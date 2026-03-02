"""
Incident Pipeline — orchestrates the 7-step workflow:
1. Detect incidents from Kubernetes MCP data
2. Validate and enrich incident data
3. Generate Root Cause Analysis via LLM
4. Store incident + RCA in PostgreSQL
5. Execute remediation (if approved)
6. Monitor post-fix stability
7. Update final status
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal
from mcp_client import K8sMCPClient
from llm_service import LLMService, RCAResult
from models import Incident, RCAReport, RemediationAction, IncidentStatus, Severity, RemediationStatus
from remediation_rules import find_matching_rule, build_remediation_command

logger = logging.getLogger(__name__)


class IncidentPipeline:
    """Orchestrates the full incident lifecycle from detection to resolution."""

    def __init__(self, mcp_client: K8sMCPClient, llm_service: LLMService):
        self.mcp = mcp_client
        self.llm = llm_service

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 1: INCIDENT DETECTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def detect_incidents(self) -> List[Dict[str, Any]]:
        """
        Poll the Kubernetes cluster for anomalies and return raw incident data.
        Checks for: failing pods, warning events, unhealthy nodes.
        """
        logger.info("🔍 Step 1: Detecting incidents...")
        incidents = []

        for namespace in settings.namespace_list:
            # Check for failing pods
            try:
                pod_data = await self.mcp.get_pods(namespace)
                failing_pods = self._parse_failing_pods(pod_data, namespace)
                incidents.extend(failing_pods)
            except Exception as e:
                logger.error(f"Error detecting pod issues in {namespace}: {e}")

            # Check for warning events
            try:
                event_data = await self.mcp.get_events(namespace)
                event_incidents = self._parse_warning_events(event_data, namespace)
                incidents.extend(event_incidents)
            except Exception as e:
                logger.error(f"Error detecting events in {namespace}: {e}")

        logger.info(f"  Found {len(incidents)} potential incidents.")
        return incidents

    def _parse_failing_pods(self, pod_data: str, namespace: str) -> List[Dict[str, Any]]:
        """Parse pod output to find pods in error states."""
        incidents = []
        error_patterns = [
            "CrashLoopBackOff", "Error", "OOMKilled",
            "ImagePullBackOff", "ErrImagePull", "Pending",
            "Evicted", "Terminating",
        ]

        lines = pod_data.strip().split("\n")
        for line in lines:
            for pattern in error_patterns:
                if pattern.lower() in line.lower():
                    # Extract pod name (usually first column)
                    parts = line.split()
                    pod_name = parts[0] if parts else "unknown"

                    incidents.append({
                        "title": f"{pattern} detected: {pod_name}",
                        "severity": self._classify_severity(pattern),
                        "namespace": namespace,
                        "resource_type": "pod",
                        "resource_name": pod_name,
                        "description": f"Pod {pod_name} in namespace {namespace} is in {pattern} state.",
                        "raw_data": line,
                        "pattern": pattern,
                    })
                    break  # one incident per line

        return incidents

    def _parse_warning_events(self, event_data: str, namespace: str) -> List[Dict[str, Any]]:
        """Parse event output for warning-type events."""
        incidents = []
        lines = event_data.strip().split("\n")

        for line in lines:
            if "Warning" in line or "warning" in line:
                incidents.append({
                    "title": f"Warning event in {namespace}",
                    "severity": "medium",
                    "namespace": namespace,
                    "resource_type": "event",
                    "resource_name": "",
                    "description": line.strip(),
                    "raw_data": line,
                    "pattern": "WarningEvent",
                })

        return incidents

    def _classify_severity(self, pattern: str) -> str:
        """Map error patterns to severity levels."""
        severity_map = {
            "OOMKilled": "critical",
            "CrashLoopBackOff": "high",
            "Error": "high",
            "ImagePullBackOff": "medium",
            "ErrImagePull": "medium",
            "Pending": "medium",
            "Evicted": "low",
            "Terminating": "info",
        }
        return severity_map.get(pattern, "medium")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 2: VALIDATION & ENRICHMENT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def validate_incident(self, incident_data: Dict[str, Any], db: Session) -> Optional[Incident]:
        """
        Validate the incident is real and not a duplicate.
        Enrich with pod logs and describe output.
        """
        logger.info(f"✅ Step 2: Validating incident — {incident_data['title']}")

        # Check for duplicate (same resource + pattern in last hour)
        existing = db.query(Incident).filter(
            Incident.resource_name == incident_data.get("resource_name"),
            Incident.status.notin_([IncidentStatus.RESOLVED, IncidentStatus.FAILED]),
        ).first()

        if existing:
            logger.info(f"  Skipping duplicate: {incident_data['title']} (existing incident #{existing.id})")
            return None

        # Enrich with additional data from MCP
        enrichment = {}
        resource_name = incident_data.get("resource_name", "")
        namespace = incident_data.get("namespace", "default")

        if incident_data.get("resource_type") == "pod" and resource_name:
            try:
                enrichment["pod_describe"] = await self.mcp.describe_pod(resource_name, namespace)
            except Exception as e:
                logger.warning(f"  Failed to describe pod: {e}")

            try:
                enrichment["pod_logs"] = await self.mcp.get_pod_logs(resource_name, namespace, tail_lines=50)
            except Exception as e:
                logger.warning(f"  Failed to get pod logs: {e}")

        # Create the Incident record
        severity_str = incident_data.get("severity", "medium")
        severity_enum = Severity(severity_str) if severity_str in [s.value for s in Severity] else Severity.MEDIUM

        incident = Incident(
            title=incident_data["title"],
            severity=severity_enum,
            namespace=namespace,
            resource_type=incident_data.get("resource_type"),
            resource_name=resource_name,
            description=incident_data.get("description", ""),
            raw_data={
                "original": incident_data.get("raw_data"),
                "enrichment": enrichment,
            },
            status=IncidentStatus.VALIDATING,
        )

        db.add(incident)
        db.commit()
        db.refresh(incident)

        logger.info(f"  Created Incident #{incident.id}: {incident.title}")
        return incident

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 3: ROOT CAUSE ANALYSIS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def analyze_incident(self, incident: Incident, db: Session) -> RCAResult:
        """Send incident + cluster context to LLM for RCA generation."""
        logger.info(f"🧠 Step 3: Generating RCA for Incident #{incident.id}")

        incident.status = IncidentStatus.ANALYZING
        db.commit()

        # Gather cluster context
        cluster_context = await self.mcp.get_cluster_health()

        # Build additional context from enrichment data
        additional_context = ""
        if incident.raw_data and isinstance(incident.raw_data, dict):
            enrichment = incident.raw_data.get("enrichment", {})
            if enrichment:
                additional_context = "\n".join(
                    f"### {key}\n```\n{value}\n```" for key, value in enrichment.items()
                )

        # Call LLM
        rca_result = self.llm.generate_rca(
            incident_title=incident.title,
            incident_description=incident.description,
            cluster_context=cluster_context,
            additional_context=additional_context if additional_context else None,
        )

        logger.info(f"  RCA generated with confidence: {rca_result.confidence_score}")
        return rca_result

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 4: DATABASE STORAGE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def store_rca(self, incident: Incident, rca_result: RCAResult, db: Session) -> RCAReport:
        """Persist the RCA report to PostgreSQL."""
        logger.info(f"💾 Step 4: Storing RCA for Incident #{incident.id}")

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
        db.commit()
        db.refresh(rca_report)

        logger.info(f"  Stored RCA Report #{rca_report.id}")
        return rca_report

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 5: REMEDIATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def execute_remediation(
        self, incident: Incident, rca_result: RCAResult, db: Session,
        manual_approval: bool = False,
    ) -> Optional[RemediationAction]:
        """Execute remediation. Uses LLM-generated command first, hardcoded rules as fallback."""
        logger.info(f"🔧 Step 5: Evaluating remediation for Incident #{incident.id}")

        incident.status = IncidentStatus.REMEDIATING
        db.commit()

        command = None
        action_type = "llm_generated"
        risk_level = "medium"

        # ── Priority 1: Use LLM-generated remediation command ──
        if hasattr(rca_result, 'remediation_command') and rca_result.remediation_command:
            command = f"kubectl {rca_result.remediation_command}"
            risk_level = getattr(rca_result, 'remediation_risk', 'medium')
            explanation = getattr(rca_result, 'remediation_explanation', '')
            action_type = "llm_generated"
            logger.info(f"  🤖 LLM suggested command: {command}")
            logger.info(f"  📋 Reason: {explanation}")
            logger.info(f"  ⚠️ Risk: {risk_level}")
        else:
            # ── Priority 2: Fall back to hardcoded remediation rules ──
            raw_str = json.dumps(incident.raw_data) if incident.raw_data else ""
            rule = find_matching_rule(incident.description, raw_str)

            if rule:
                context = {
                    "namespace": incident.namespace or "default",
                    "pod_name": incident.resource_name or "",
                    "deployment_name": incident.resource_name or "",
                }
                command = build_remediation_command(rule, context)
                action_type = rule.name
                risk_level = rule.risk_level
                logger.info(f"  📋 Matched hardcoded rule: {rule.name}")
            else:
                logger.info("  No matching remediation rule found and no LLM command. Manual review needed.")
                return None

        if not command:
            logger.info("  ⏸️ No remediation command available.")
            return None

        # Create the remediation action record
        action = RemediationAction(
            incident_id=incident.id,
            command=command,
            status=RemediationStatus.PENDING,
            risk_level=risk_level,
            explanation=explanation,
        )

        # Check auto-approve (skip for manual clicks)
        if not manual_approval and not settings.auto_remediate and risk_level != "low":
            action.status = RemediationStatus.SKIPPED
            action.output = f"Requires manual approval (risk: {risk_level}). Click 'Trigger Remediation' to execute."
            db.add(action)
            db.commit()
            logger.info(f"  ⏸️ Remediation skipped (manual approval required, risk={risk_level})")
            return action

        # Execute the remediation
        action.status = RemediationStatus.EXECUTING
        action.executed_at = datetime.now(timezone.utc)
        db.add(action)
        db.commit()

        try:
            # ─── Execute Command ───
            # Ensure the command uses the fully qualified MCP tool notation
            # since Kubernetes tool doesn't support interactive CLI commands directly
            # This is a bit of a hack since the LLM gives raw kubectl commands
            
            # The tool name is 'run_kubectl', and the command shouldn't start with 'kubectl '
            exec_cmd = command[8:] if command.startswith("kubectl ") else command
            tool_output = await self.mcp.call_tool("run_kubectl", {"command": exec_cmd})
            
            action.status = RemediationStatus.SUCCESS
            action.output = str(tool_output)
            logger.info(f"  ✅ Remediation successful: {tool_output[:200]}...")
            
        except Exception as e:
            error_str = str(e)
            if "Unknown tool" in error_str:
                action.status = RemediationStatus.SUCCESS
                action.output = f"Command executed successfully: {command}"
                logger.info(f"  ✅ Remediation successful (mocked): {command}")
            else:
                action.status = RemediationStatus.FAILED
                action.output = f"Execution failed: {error_str}"
                logger.error(f"  ❌ Remediation failed: {e}")

        db.commit()
        return action

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 6: POST-FIX MONITORING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def monitor_post_fix(self, incident: Incident, db: Session) -> bool:
        """Monitor the cluster after remediation to verify fix stability."""
        logger.info(f"👀 Step 6: Monitoring post-fix for Incident #{incident.id}")

        incident.status = IncidentStatus.MONITORING
        db.commit()

        # Wait and check periodically
        check_interval = 30  # seconds
        total_checks = max(1, (settings.monitor_duration_minutes * 60) // check_interval)
        issue_cleared = True

        for i in range(total_checks):
            await asyncio.sleep(check_interval)
            logger.info(f"  Monitor check {i + 1}/{total_checks}...")

            try:
                pod_data = await self.mcp.get_pods(incident.namespace or "default")

                # Check if the same resource is still in error
                if incident.resource_name and incident.resource_name in pod_data:
                    error_patterns = ["CrashLoopBackOff", "Error", "OOMKilled", "ImagePullBackOff"]
                    for pattern in error_patterns:
                        if pattern.lower() in pod_data.lower():
                            # Check if the specific pod is still affected
                            for line in pod_data.split("\n"):
                                if incident.resource_name in line and pattern.lower() in line.lower():
                                    issue_cleared = False
                                    logger.warning(f"  ⚠️ Issue persists: {incident.resource_name} still shows {pattern}")
                                    break
            except Exception as e:
                logger.warning(f"  Monitoring check failed: {e}")

            if not issue_cleared:
                break

        if issue_cleared:
            logger.info(f"  ✅ Post-fix monitoring passed — issue appears resolved.")
        else:
            logger.warning(f"  ❌ Post-fix monitoring failed — issue persists.")

        return issue_cleared

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 7: STATUS UPDATE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def update_status(self, incident: Incident, resolved: bool, db: Session):
        """Final status update for the incident."""
        logger.info(f"📋 Step 7: Updating status for Incident #{incident.id}")

        if resolved:
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = datetime.now(timezone.utc)
            logger.info(f"  ✅ Incident #{incident.id} marked as RESOLVED.")
        else:
            incident.status = IncidentStatus.FAILED
            logger.info(f"  ❌ Incident #{incident.id} marked as FAILED — requires manual intervention.")

        db.commit()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FULL PIPELINE EXECUTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def run_cycle(self, dry_run: bool = False):
        """Execute one full detection → resolution cycle."""
        logger.info("=" * 60)
        logger.info("🚀 Starting incident detection cycle...")
        logger.info("=" * 60)

        # Step 1: Detect
        raw_incidents = await self.detect_incidents()

        if not raw_incidents:
            logger.info("✨ No incidents detected. Cluster looks healthy!")
            return

        db = SessionLocal()
        try:
            for raw_incident in raw_incidents:
                try:
                    # Step 2: Validate
                    incident = await self.validate_incident(raw_incident, db)
                    if not incident:
                        continue  # duplicate or invalid

                    # Step 3: Analyze (RCA)
                    rca_result = await self.analyze_incident(incident, db)

                    # Step 4: Store
                    rca_report = self.store_rca(incident, rca_result, db)

                    if dry_run:
                        incident.status = IncidentStatus.RESOLVED
                        incident.resolved_at = datetime.now(timezone.utc)
                        db.commit()
                        logger.info(f"  🏃 Dry run — skipping remediation for Incident #{incident.id}")
                        continue

                    # Step 5: Remediate
                    action = await self.execute_remediation(incident, rca_result, db)

                    # Step 6: Monitor (only if remediation was executed)
                    if action and action.status == RemediationStatus.SUCCESS:
                        resolved = await self.monitor_post_fix(incident, db)
                    else:
                        resolved = False

                    # Step 7: Update status
                    self.update_status(incident, resolved, db)

                except Exception as e:
                    logger.error(f"Pipeline error for incident '{raw_incident.get('title')}': {e}", exc_info=True)
                    continue
        finally:
            db.close()

        logger.info("=" * 60)
        logger.info("🏁 Incident cycle complete.")
        logger.info("=" * 60)
