"""
Email Alert Monitor — polls an email inbox (IMAP) for AlertManager
notification emails, parses them, and creates incidents in the database.

Flow:
  1. Connect to IMAP email server
  2. Search for unread emails from AlertManager
  3. Parse email subject/body to extract alert details
  4. Create Incident in PostgreSQL
  5. Mark email as read
  6. Trigger async RCA via LLM + MCP
"""

import asyncio
import email
import imaplib
import json
import logging
import re
from datetime import datetime, timezone
from email.header import decode_header
from typing import Dict, List, Optional, Tuple

from config import settings
from database import SessionLocal
from models import Incident, IncidentStatus, Severity, RCAReport
from mcp_client import K8sMCPClient
from llm_service import LLMService
from incident_pipeline import IncidentPipeline
from remediation_rules import find_matching_rule, build_remediation_command

logger = logging.getLogger("email-monitor")


def _decode_header_value(value: str) -> str:
    """Decode email header value (may be encoded)."""
    decoded_parts = decode_header(value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def _map_severity(text: str) -> Severity:
    """Extract severity from email content."""
    text_lower = text.lower()
    if "critical" in text_lower or "crit" in text_lower:
        return Severity.CRITICAL
    elif "error" in text_lower or "high" in text_lower:
        return Severity.HIGH
    elif "warning" in text_lower or "warn" in text_lower:
        return Severity.MEDIUM
    elif "info" in text_lower:
        return Severity.LOW
    return Severity.MEDIUM


def _extract_alert_details(subject: str, body: str) -> Dict:
    """
    Parse AlertManager email to extract alert details.
    AlertManager emails typically have a structured format with labels.
    """
    details = {
        "alertname": "",
        "namespace": "default",
        "pod": "",
        "severity": "warning",
        "description": "",
        "instance": "",
        "status": "firing",
    }

    # Extract from subject — typical format: [FIRING:1] AlertName Namespace/Pod
    subject_clean = subject.strip()
    details["title"] = subject_clean

    # Check if firing or resolved
    if "[RESOLVED" in subject_clean.upper():
        details["status"] = "resolved"
    elif "[FIRING" in subject_clean.upper():
        details["status"] = "firing"

    # Extract alert name from subject
    alert_match = re.search(r'\]\s*(.+?)(?:\s*\(|$)', subject_clean)
    if alert_match:
        details["alertname"] = alert_match.group(1).strip()

    # Parse body for key-value pairs (AlertManager format)
    # Common patterns: "Label: Value" or "key = value"
    body_text = body.strip()

    # Look for alertname
    name_match = re.search(r'(?:alertname|Alert(?:\s*Name)?)\s*[=:]\s*(\S+)', body_text, re.IGNORECASE)
    if name_match:
        details["alertname"] = name_match.group(1).strip()

    # Look for namespace
    ns_match = re.search(r'namespace\s*[=:]\s*(\S+)', body_text, re.IGNORECASE)
    if ns_match:
        details["namespace"] = ns_match.group(1).strip()

    # Look for pod
    pod_match = re.search(r'pod\s*[=:]\s*(\S+)', body_text, re.IGNORECASE)
    if pod_match:
        details["pod"] = pod_match.group(1).strip()

    # Look for severity
    sev_match = re.search(r'severity\s*[=:]\s*(\S+)', body_text, re.IGNORECASE)
    if sev_match:
        details["severity"] = sev_match.group(1).strip()

    # Look for instance
    inst_match = re.search(r'instance\s*[=:]\s*(\S+)', body_text, re.IGNORECASE)
    if inst_match:
        details["instance"] = inst_match.group(1).strip()

    # Look for description/summary
    desc_match = re.search(r'(?:description|summary|message)\s*[=:]\s*(.+?)(?:\n|$)', body_text, re.IGNORECASE)
    if desc_match:
        details["description"] = desc_match.group(1).strip()

    # If no description found, use the first few lines of the body
    if not details["description"]:
        lines = [l.strip() for l in body_text.split("\n") if l.strip()]
        details["description"] = " ".join(lines[:3])[:500]

    return details


def _get_email_body(msg: email.message.Message) -> str:
    """Extract plain text body from email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
            elif content_type == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    # Simple HTML to text
                    body = re.sub(r'<[^>]+>', ' ', html)
                    body = re.sub(r'\s+', ' ', body).strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    return body


async def _run_rca_for_incident(incident_id: int):
    """Background task: run RCA via LLM for a new incident."""
    try:
        mcp_client = K8sMCPClient()
        llm_service = LLMService()

        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == incident_id).first()
            if not incident:
                logger.error(f"Incident {incident_id} not found for RCA")
                return

            logger.info(f"🔍 Starting RCA for incident #{incident.id}: {incident.title}")

            await mcp_client.connect()
            logger.info(f"✅ MCP connected for RCA")

            # Gather ONLY relevant context (not all namespaces — too slow)
            namespace = incident.namespace or "default"
            cluster_context = {}

            # Step 1: Get pods in the incident's namespace
            try:
                logger.info(f"📦 Getting pods in namespace: {namespace}")
                pods = await asyncio.wait_for(
                    mcp_client.get_pods(namespace), timeout=30
                )
                cluster_context["pods"] = pods
                logger.info(f"✅ Got pods data")
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Timeout getting pods in {namespace}")
                cluster_context["pods"] = "Timeout — could not retrieve pods"
            except Exception as e:
                logger.warning(f"Could not get pods: {e}")

            # Step 2: Get events in the namespace
            try:
                logger.info(f"📋 Getting events in namespace: {namespace}")
                events = await asyncio.wait_for(
                    mcp_client.get_events(namespace), timeout=30
                )
                cluster_context["events"] = events
                logger.info(f"✅ Got events data")
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Timeout getting events in {namespace}")
            except Exception as e:
                logger.warning(f"Could not get events: {e}")

            # Step 3: Get deployments in the namespace
            try:
                logger.info(f"📦 Getting deployments in namespace: {namespace}")
                deployments = await asyncio.wait_for(
                    mcp_client.get_deployments(namespace), timeout=30
                )
                cluster_context["deployments"] = deployments
                logger.info(f"✅ Got deployments data")
            except Exception as e:
                logger.warning(f"Could not get deployments: {e}")

            # Step 4: Get pod details — try describe and logs for relevant pods
            additional_context_parts = []
            pod_name = incident.resource_name or ""

            # If no specific pod, try to find one from pods data that matches the alert
            if not pod_name and cluster_context.get("pods"):
                pods_str = str(cluster_context["pods"])
                # Look for pods with errors
                for pattern in ["CrashLoopBackOff", "Error", "OOMKilled", "ImagePullBackOff", "Pending"]:
                    for line in pods_str.split("\n"):
                        if pattern.lower() in line.lower():
                            parts = line.split()
                            if parts:
                                pod_name = parts[0]
                                break
                    if pod_name:
                        break

            if pod_name:
                try:
                    logger.info(f"🔎 Describing pod: {pod_name}")
                    pod_desc = await asyncio.wait_for(
                        mcp_client.describe_pod(pod_name, namespace),
                        timeout=30,
                    )
                    additional_context_parts.append(f"### Pod Description\n```\n{pod_desc}\n```")
                    logger.info(f"✅ Got pod description")
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Timeout describing pod")
                except Exception as e:
                    logger.warning(f"Could not describe pod: {e}")

                try:
                    logger.info(f"📝 Getting pod logs: {pod_name}")
                    pod_logs = await asyncio.wait_for(
                        mcp_client.get_pod_logs(pod_name, namespace),
                        timeout=30,
                    )
                    additional_context_parts.append(f"### Pod Logs\n```\n{pod_logs[:5000]}\n```")
                    logger.info(f"✅ Got pod logs")
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Timeout getting pod logs")
                except Exception as e:
                    logger.warning(f"Could not get pod logs: {e}")

            # Step 5: Get node status
            try:
                logger.info(f"🖥️ Getting node status")
                nodes = await asyncio.wait_for(
                    mcp_client.get_nodes(), timeout=30
                )
                cluster_context["nodes"] = nodes
                logger.info(f"✅ Got node status")
            except Exception as e:
                logger.warning(f"Could not get nodes: {e}")

            additional_context = "\n\n".join(additional_context_parts) if additional_context_parts else None

            # Step 6: Call Claude for RCA + remediation command
            logger.info(f"🤖 Sending data to Claude for RCA generation...")
            rca_result = llm_service.generate_rca(
                incident_title=incident.title,
                incident_description=incident.description or "No description available",
                cluster_context=cluster_context,
                additional_context=additional_context,
            )
            logger.info(f"✅ Claude responded")

            if rca_result:
                # If LLM didn't provide a remediation command, compute from hardcoded rules
                if not rca_result.remediation_command:
                    raw_str = json.dumps(incident.raw_data) if incident.raw_data else ""
                    rule = find_matching_rule(incident.description or "", raw_str)
                    if rule:
                        context = {
                            "namespace": incident.namespace or "default",
                            "pod_name": incident.resource_name or "",
                            "deployment_name": incident.resource_name or "",
                        }
                        fallback_cmd = build_remediation_command(rule, context)
                        if fallback_cmd:
                            # Remove 'kubectl ' prefix since the field stores just the args
                            if fallback_cmd.startswith("kubectl "):
                                fallback_cmd = fallback_cmd[len("kubectl "):]
                            rca_result.remediation_command = fallback_cmd
                            rca_result.remediation_risk = rule.risk_level
                            rca_result.remediation_explanation = f"Matched rule: {rule.name} — {rule.description}"
                            logger.info(f"📋 Fallback command from hardcoded rule '{rule.name}': kubectl {fallback_cmd}")
                        else:
                            logger.info(f"⚠️ Matched rule '{rule.name}' but no command generated")
                    else:
                        logger.info(f"⚠️ No matching hardcoded rule found either")
                else:
                    logger.info(f"🤖 LLM suggested command: kubectl {rca_result.remediation_command}")
                    logger.info(f"   Risk: {rca_result.remediation_risk}")
                    logger.info(f"   Reason: {rca_result.remediation_explanation}")

                rca_report = RCAReport(
                    incident_id=incident.id,
                    root_cause=rca_result.root_cause,
                    analysis=rca_result.analysis,
                    recommendations=rca_result.recommendations,
                    confidence_score=rca_result.confidence_score,
                    llm_model=settings.bedrock_model_id,
                    raw_response=json.dumps(rca_result.model_dump()),
                )
                db.add(rca_report)
                incident.status = IncidentStatus.ANALYZING
                db.commit()
                logger.info(f"✅ RCA saved for incident #{incident.id}: {rca_result.root_cause[:100]}")

            try:
                await mcp_client.disconnect()
            except Exception:
                pass  # MCP stdio cleanup error on Windows — safe to ignore
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ RCA generation failed for incident #{incident_id}: {e}", exc_info=True)


class EmailAlertMonitor:
    """Monitors an email inbox for AlertManager notification emails."""

    def __init__(self):
        self.imap_server = settings.email_imap_server
        self.imap_port = settings.email_imap_port
        self.email_address = settings.email_address
        self.email_password = settings.email_password
        self.alert_sender = settings.alert_sender_email
        self.poll_interval = settings.email_poll_interval_seconds
        self._mail: Optional[imaplib.IMAP4_SSL] = None

    def connect(self):
        """Connect to the IMAP server."""
        logger.info(f"📧 Connecting to email: {self.email_address} via {self.imap_server}:{self.imap_port}")
        self._mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        self._mail.login(self.email_address, self.email_password)
        logger.info("✅ Connected to email server.")

    def disconnect(self):
        """Disconnect from the IMAP server."""
        if self._mail:
            try:
                self._mail.logout()
            except Exception:
                pass
            self._mail = None
            logger.info("🔌 Disconnected from email server.")

    def _fetch_unread_alerts(self) -> List[Tuple[str, str, str]]:
        """
        Fetch unread alert emails.
        Returns list of (message_id, subject, body) tuples.
        """
        if not self._mail:
            raise RuntimeError("Not connected to email server. Call connect() first.")

        self._mail.select("INBOX")

        # Build search criteria
        criteria = '(UNSEEN)'
        if self.alert_sender:
            criteria = f'(UNSEEN FROM "{self.alert_sender}")'

        status, message_ids = self._mail.search(None, criteria)
        if status != "OK" or not message_ids[0]:
            return []

        results = []
        for msg_id in message_ids[0].split():
            try:
                status, msg_data = self._mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = _decode_header_value(msg.get("Subject", ""))
                body = _get_email_body(msg)

                results.append((msg_id.decode(), subject, body))

                # Mark as read
                self._mail.store(msg_id, "+FLAGS", "\\Seen")

            except Exception as e:
                logger.error(f"Error processing email {msg_id}: {e}")

        return results

    async def process_alerts(self) -> List[int]:
        """
        Check for new alert emails and create incidents.
        Returns list of created incident IDs.
        """
        alerts = self._fetch_unread_alerts()
        if not alerts:
            return []

        logger.info(f"📨 Found {len(alerts)} new alert email(s)")
        created_ids = []

        db = SessionLocal()
        try:
            for msg_id, subject, body in alerts:
                details = _extract_alert_details(subject, body)

                # Skip resolved alerts — just log them
                if details["status"] == "resolved":
                    logger.info(f"✅ Resolved alert: {subject}")
                    # Try to auto-resolve matching incidents
                    existing = db.query(Incident).filter(
                        Incident.title.contains(details.get("alertname", "")),
                        Incident.source == "email",
                        Incident.status.notin_([IncidentStatus.RESOLVED, IncidentStatus.FAILED]),
                    ).all()
                    for inc in existing:
                        inc.status = IncidentStatus.RESOLVED
                        inc.resolved_at = datetime.now(timezone.utc)
                    db.commit()
                    continue

                # Check for duplicate
                existing = db.query(Incident).filter(
                    Incident.title == details.get("title", subject),
                    Incident.source == "email",
                    Incident.status.notin_([IncidentStatus.RESOLVED, IncidentStatus.FAILED]),
                ).first()
                if existing:
                    logger.info(f"⏭️ Skipping duplicate alert email: {subject}")
                    continue

                # Create incident
                severity = _map_severity(details["severity"])
                pod_name = details.get("pod", "")

                incident = Incident(
                    title=details.get("title", subject)[:500],
                    description=details.get("description", body[:1000]),
                    severity=severity,
                    namespace=details.get("namespace", "default"),
                    resource_type="Pod" if pod_name else "Cluster",
                    resource_name=pod_name or details.get("instance", ""),
                    status=IncidentStatus.DETECTED,
                    source="email",
                    alert_fingerprint=f"email-{msg_id}",
                    raw_data={
                        "email_subject": subject,
                        "email_body": body[:5000],
                        "parsed_details": details,
                    },
                )
                db.add(incident)
                db.flush()

                logger.info(f"🆕 Incident #{incident.id} created from email: {subject}")
                created_ids.append(incident.id)

            db.commit()
        finally:
            db.close()

        return created_ids

    async def run_loop(self, shutdown_event: asyncio.Event):
        """Main loop — use IMAP IDLE for push-based instant email monitoring."""
        logger.info(f"📧 Email Alert Monitor started (listening in real-time via IMAP IDLE)")
        logger.info(f"   Email: {self.email_address}")
        logger.info(f"   Alert sender filter: {self.alert_sender or 'ANY'}")

        self.connect()

        try:
            while not shutdown_event.is_set():
                try:
                    # 1. Process any existing unread alerts immediately
                    incident_ids = await self.process_alerts()
                    for inc_id in incident_ids:
                        asyncio.create_task(_run_rca_for_incident(inc_id))

                    # 2. Wait for a short interval before checking again
                    # We use a 5-second fast-poll which gives near-instant results
                    # without the complexity and unreliability of raw IMAP IDLE sockets
                    await asyncio.wait_for(
                        shutdown_event.wait(),
                        timeout=5,
                    )
                    break
                except asyncio.TimeoutError:
                    pass # Loop around and poll again
                except imaplib.IMAP4.abort as e:
                    logger.warning(f"IMAP connection dropped (EOF). Reconnecting...")
                    await asyncio.sleep(2)
                    try:
                        self.connect()
                    except Exception as reconnect_err:
                        logger.error(f"Reconnect failed: {reconnect_err}")
                except Exception as e:
                    logger.error(f"Email monitor error: {e}", exc_info=True)
                    # Reconnect on error
                    await asyncio.sleep(5)
                    try:
                        self.connect()
                    except Exception as reconnect_err:
                        logger.error(f"Reconnect failed: {reconnect_err}")

        finally:
            self.disconnect()
            logger.info("📧 Email Alert Monitor stopped.")
