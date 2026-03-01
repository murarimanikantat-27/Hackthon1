"""
FastAPI application — REST API + web dashboard for incident management.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fpdf import FPDF
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from config import settings
from database import get_db, SessionLocal
from models import Incident, RCAReport, RemediationAction, IncidentStatus, Severity, RemediationStatus
from remediation_rules import get_all_rules
from mcp_client import K8sMCPClient
from llm_service import LLMService
from incident_pipeline import IncidentPipeline

# ─── App Setup ───
app = FastAPI(
    title="K8s Incident Management Agent",
    description="Kubernetes incident detection, RCA, and remediation dashboard",
    version="1.0.0",
)

# Templates
TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ─── Pydantic Response Models ───

class IncidentSummary(BaseModel):
    id: int
    title: str
    severity: str
    namespace: str
    resource_type: Optional[str]
    resource_name: Optional[str]
    status: str
    detected_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class RCADetail(BaseModel):
    id: int
    root_cause: str
    analysis: Optional[str]
    recommendations: Optional[list]
    confidence_score: float
    llm_model: Optional[str]
    created_at: datetime
    remediation_command: Optional[str] = ""
    remediation_risk: Optional[str] = ""
    remediation_explanation: Optional[str] = ""
    
    executive_summary: Optional[str] = ""
    incident_detection: Optional[str] = ""
    incident_timeline: Optional[list] = []
    impact_assessment: Optional[str] = ""
    resolution_actions: Optional[str] = ""
    preventive_measures: Optional[str] = ""
    lessons_learned: Optional[str] = ""
    final_summary: Optional[str] = ""

    class Config:
        from_attributes = True


class RemediationDetail(BaseModel):
    id: int
    action_type: Optional[str]
    command: Optional[str]
    result: Optional[str]
    status: str
    executed_at: Optional[datetime]

    class Config:
        from_attributes = True


class IncidentFull(BaseModel):
    incident: IncidentSummary
    rca_reports: List[RCADetail]
    remediation_actions: List[RemediationDetail]


class DashboardStats(BaseModel):
    total_incidents: int
    active_incidents: int
    resolved_incidents: int
    failed_incidents: int
    critical_count: int
    high_count: int
    avg_confidence: float


# ─── AlertManager Webhook Models ───

import logging
alert_logger = logging.getLogger("alertmanager-webhook")


class AlertLabel(BaseModel):
    alertname: str = ""
    severity: str = "warning"
    namespace: str = "default"
    pod: str = ""
    container: str = ""
    instance: str = ""
    job: str = ""
    # Allow extra labels
    class Config:
        extra = "allow"


class AlertAnnotation(BaseModel):
    summary: str = ""
    description: str = ""
    runbook_url: str = ""
    class Config:
        extra = "allow"


class Alert(BaseModel):
    status: str = "firing"  # "firing" or "resolved"
    labels: AlertLabel = AlertLabel()
    annotations: AlertAnnotation = AlertAnnotation()
    startsAt: str = ""
    endsAt: str = ""
    generatorURL: str = ""
    fingerprint: str = ""


class AlertManagerPayload(BaseModel):
    version: str = "4"
    groupKey: str = ""
    status: str = "firing"
    receiver: str = ""
    alerts: List[Alert] = []
    groupLabels: dict = {}
    commonLabels: dict = {}
    commonAnnotations: dict = {}
    externalURL: str = ""


# ─── API Endpoints ───

@app.get("/api/incidents", response_model=List[IncidentSummary])
def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    namespace: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """List incidents with optional filters."""
    query = db.query(Incident)

    if status:
        query = query.filter(Incident.status == status)
    if severity:
        query = query.filter(Incident.severity == severity)
    if namespace:
        query = query.filter(Incident.namespace == namespace)

    incidents = query.order_by(desc(Incident.detected_at)).limit(limit).all()
    return [
        IncidentSummary(
            id=i.id,
            title=i.title,
            severity=i.severity.value if i.severity else "medium",
            namespace=i.namespace or "default",
            resource_type=i.resource_type,
            resource_name=i.resource_name,
            status=i.status.value if i.status else "detected",
            detected_at=i.detected_at,
            resolved_at=i.resolved_at,
        )
        for i in incidents
    ]


@app.get("/api/incidents/{incident_id}", response_model=IncidentFull)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    """Get full incident detail with RCA and remediation history."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Build RCA reports with LLM-generated remediation command
    rca_details = []
    for r in incident.rca_reports:
        rem_cmd, rem_risk, rem_expl = "", "", ""
        exec_sum, inc_det, inc_time = "", "", []
        imp_ass, res_act, prev_mea, less_lrn, fin_sum = "", "", "", "", ""

        if r.raw_response:
            try:
                raw = json.loads(r.raw_response)
                rem_cmd = raw.get("remediation_command", "")
                rem_risk = raw.get("remediation_risk", "")
                rem_expl = raw.get("remediation_explanation", "")
                
                exec_sum = raw.get("executive_summary", "")
                inc_det = raw.get("incident_detection", "")
                inc_time = raw.get("incident_timeline", [])
                
                # Helper to gracefully parse either lists or strings from LLM
                def _to_str(val):
                    if isinstance(val, list):
                        return "\n".join(f"- {v}" for v in val)
                    return str(val) if val else ""

                imp_ass = _to_str(raw.get("impact_assessment", ""))
                res_act = _to_str(raw.get("resolution_actions", ""))
                prev_mea = _to_str(raw.get("preventive_measures", ""))
                less_lrn = _to_str(raw.get("lessons_learned", ""))
                fin_sum = _to_str(raw.get("final_summary", ""))
            except (json.JSONDecodeError, TypeError):
                pass
        rca_details.append(RCADetail(
            id=r.id,
            root_cause=r.root_cause,
            analysis=r.analysis,
            recommendations=r.recommendations,
            confidence_score=r.confidence_score or 0.0,
            llm_model=r.llm_model,
            created_at=r.created_at,
            remediation_command=rem_cmd,
            remediation_risk=rem_risk,
            remediation_explanation=rem_expl,
            executive_summary=exec_sum,
            incident_detection=inc_det,
            incident_timeline=inc_time,
            impact_assessment=imp_ass,
            resolution_actions=res_act,
            preventive_measures=prev_mea,
            lessons_learned=less_lrn,
            final_summary=fin_sum,
        ))

    try:
        return IncidentFull(
            incident=IncidentSummary(
                id=incident.id,
                title=incident.title,
                severity=incident.severity.value if incident.severity else "medium",
                namespace=incident.namespace or "default",
                resource_type=incident.resource_type,
                resource_name=incident.resource_name,
                status=incident.status.value if incident.status else "detected",
                detected_at=incident.detected_at,
                resolved_at=incident.resolved_at,
            ),
            rca_reports=rca_details,
            remediation_actions=[
                RemediationDetail(
                    id=a.id,
                    action_type=a.action_type,
                    command=a.command,
                    result=a.result,
                    status=a.status.value if a.status else "pending",
                    executed_at=a.executed_at,
                )
                for a in incident.remediation_actions
            ],
        )
    except Exception as e:
        alert_logger.error(f"Error fetching incident: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/api/incidents/{incident_id}/pdf")
def download_incident_pdf(incident_id: int, db: Session = Depends(get_db)):
    """Generate and download a formal PDF report for the incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Pick the latest RCA report
    rca = incident.rca_reports[0] if incident.rca_reports else None
    
    # Initialize PDF
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Title
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(0, 10, f"Root Cause Analysis Report: INC-{incident.id}", ln=True, align="L")
    pdf.ln(5)

    # Metadata
    pdf.set_font("helvetica", size=11)
    date_str = incident.detected_at.strftime("%B %d, %Y")
    severity_str = incident.severity.name.capitalize() if hasattr(incident.severity, 'name') else str(incident.severity).capitalize()
    
    pdf.cell(0, 6, f"Incident ID: INC-{incident.id}", ln=True)
    pdf.cell(0, 6, f"Date: {date_str}", ln=True)
    pdf.cell(0, 6, f"Prepared By: AI-Assisted SRE System", ln=True)
    pdf.cell(0, 6, f"Severity: {severity_str}", ln=True)
    pdf.cell(0, 6, f"Category: Resource Exhaustion (Kubernetes / JVM)", ln=True)
    pdf.ln(10)

    if not rca:
        pdf.set_font("helvetica", style="I", size=12)
        pdf.cell(0, 10, "No structured Root Cause Analysis data is available for this incident yet.", ln=True)
        
        pdf_bytes = pdf.output()
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=INC-{incident.id}_RCA_Report.pdf"})

    # Parse raw response robustly just like get_incident
    rem_cmd = ""
    exec_sum, inc_det, inc_time = "", "", []
    imp_ass, res_act, prev_mea, less_lrn, fin_sum = "", "", "", "", ""
    if rca.raw_response:
        try:
            raw = json.loads(rca.raw_response)
            rem_cmd = raw.get("remediation_command", "")
            exec_sum = raw.get("executive_summary", "")
            inc_det = raw.get("incident_detection", "")
            inc_time = raw.get("incident_timeline", [])
            
            def _to_str(val):
                if isinstance(val, list):
                    return "\n".join(f"- {v}" for v in val)
                return str(val) if val else ""
            
            imp_ass = _to_str(raw.get("impact_assessment", ""))
            res_act = _to_str(raw.get("resolution_actions", ""))
            prev_mea = _to_str(raw.get("preventive_measures", ""))
            less_lrn = _to_str(raw.get("lessons_learned", ""))
            fin_sum = _to_str(raw.get("final_summary", ""))
        except Exception:
            pass

    # Helper function for sections
    def add_section(title, content):
        if not content:
            return
        pdf.set_font("helvetica", style="B", size=12)
        pdf.cell(0, 10, title, ln=True, border='B')
        pdf.ln(3)
        pdf.set_font("helvetica", size=10)
        pdf.multi_cell(0, 5, content)
        pdf.ln(8)

    # 1. Executive Summary
    add_section("1. Executive Summary", exec_sum or "No executive summary available.")
    
    # 2. Incident Detection
    add_section("2. Incident Detection", inc_det or "No detection details provided.")
    
    # 3. Incident Timeline
    if inc_time:
        timeline_str = "\n".join(f"• {t}" for t in inc_time)
        add_section("3. Incident Timeline (UTC)", timeline_str)
        
    # 4. Root Cause Analysis
    pdf.set_font("helvetica", style="B", size=12)
    pdf.cell(0, 10, "4. Root Cause Analysis", ln=True, border='B')
    pdf.ln(3)
    pdf.set_font("helvetica", style="B", size=10)
    pdf.cell(0, 6, "Primary Root Cause", ln=True)
    pdf.set_font("helvetica", size=10)
    pdf.multi_cell(0, 5, rca.root_cause or "")
    pdf.ln(2)
    
    conf = int((rca.confidence_score or 0) * 100)
    conf_level = "High" if conf >= 70 else ("Medium" if conf >= 40 else "Low")
    pdf.cell(0, 6, f"Confidence Level: {rca.confidence_score or 0} ({conf_level})", ln=True)
    pdf.ln(2)
    
    pdf.set_font("helvetica", style="B", size=10)
    pdf.cell(0, 6, "Supporting Evidence", ln=True)
    pdf.set_font("helvetica", size=10)
    pdf.multi_cell(0, 5, rca.analysis or "")
    pdf.ln(8)
    
    # 5. Impact Assessment
    add_section("5. Impact Assessment", imp_ass or "No impact assessment provided.")
    
    # 6. Resolution Actions
    pdf.set_font("helvetica", style="B", size=12)
    pdf.cell(0, 10, "6. Resolution Actions (Automated)", ln=True, border='B')
    pdf.ln(3)
    pdf.set_font("helvetica", size=10)
    pdf.multi_cell(0, 5, res_act or "No resolution actions logged.")
    if rem_cmd:
        pdf.ln(2)
        pdf.set_font("helvetica", style="B", size=10)
        pdf.cell(0, 6, "Automated Remediation Command executed:", ln=True)
        pdf.set_font("courier", size=9)
        pdf.set_fill_color(240, 240, 240)
        pdf.multi_cell(0, 6, f"$ kubectl {rem_cmd}", fill=True)
    pdf.ln(8)
    
    # 7. Preventive Measures
    add_section("7. Preventive Measures", prev_mea or "No preventive measures recommended.")
    
    # 8. Lessons Learned
    add_section("8. Lessons Learned", less_lrn or "No lessons learned recorded.")
    
    # 9. Final Summary
    add_section("9. Final Summary", fin_sum or "No final summary available.")

    # Return as response
    pdf_bytes = pdf.output()
    headers = {
        "Content-Disposition": f"attachment; filename=INC-{incident.id}_RCA_Report.pdf"
    }
    return Response(content=bytes(pdf_bytes), media_type="application/pdf", headers=headers)


@app.post("/api/incidents/{incident_id}/remediate")
async def trigger_remediation(incident_id: int, db: Session = Depends(get_db)):
    """Manually trigger remediation for an incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Initialize MCP client and pipeline
    mcp_client = K8sMCPClient()
    llm_service = LLMService()
    pipeline = IncidentPipeline(mcp_client, llm_service)

    try:
        await mcp_client.connect()

        # Get the latest RCA
        rca_report = db.query(RCAReport).filter(
            RCAReport.incident_id == incident_id
        ).order_by(desc(RCAReport.created_at)).first()

        if not rca_report:
            raise HTTPException(status_code=400, detail="No RCA found for this incident")

        from llm_service import RCAResult

        # Try to recover LLM-generated remediation command from stored raw_response
        remediation_command = ""
        remediation_risk = "medium"
        remediation_explanation = ""
        if rca_report.raw_response:
            try:
                raw_data = json.loads(rca_report.raw_response)
                remediation_command = raw_data.get("remediation_command", "")
                remediation_risk = raw_data.get("remediation_risk", "medium")
                remediation_explanation = raw_data.get("remediation_explanation", "")
            except (json.JSONDecodeError, TypeError):
                pass

        rca_result = RCAResult(
            root_cause=rca_report.root_cause,
            analysis=rca_report.analysis or "",
            severity_assessment=incident.severity.value if incident.severity else "medium",
            recommendations=rca_report.recommendations or [],
            immediate_actions=[],
            preventive_measures=[],
            confidence_score=rca_report.confidence_score or 0.0,
            affected_components=[],
            estimated_impact="",
            remediation_command=remediation_command,
            remediation_risk=remediation_risk,
            remediation_explanation=remediation_explanation,
        )

        action = await pipeline.execute_remediation(incident, rca_result, db, manual_approval=True)

        # Update incident status based on remediation result
        if action and action.status == RemediationStatus.SUCCESS:
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = datetime.now(timezone.utc)
            db.commit()
        elif action and action.status == RemediationStatus.FAILED:
            incident.status = IncidentStatus.FAILED
            db.commit()

        return {
            "status": "success" if action else "no_action",
            "action": {
                "id": action.id,
                "type": action.action_type,
                "command": action.command,
                "result": action.result,
                "status": action.status.value,
            } if action else None,
        }
    finally:
        try:
            await mcp_client.disconnect()
        except Exception:
            pass


@app.get("/api/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get summary statistics for the dashboard."""
    total = db.query(func.count(Incident.id)).scalar() or 0
    active = db.query(func.count(Incident.id)).filter(
        Incident.status.notin_([IncidentStatus.RESOLVED, IncidentStatus.FAILED])
    ).scalar() or 0
    resolved = db.query(func.count(Incident.id)).filter(
        Incident.status == IncidentStatus.RESOLVED
    ).scalar() or 0
    failed = db.query(func.count(Incident.id)).filter(
        Incident.status == IncidentStatus.FAILED
    ).scalar() or 0
    critical = db.query(func.count(Incident.id)).filter(
        Incident.severity == Severity.CRITICAL
    ).scalar() or 0
    high = db.query(func.count(Incident.id)).filter(
        Incident.severity == Severity.HIGH
    ).scalar() or 0
    avg_conf = db.query(func.avg(RCAReport.confidence_score)).scalar() or 0.0

    return DashboardStats(
        total_incidents=total,
        active_incidents=active,
        resolved_incidents=resolved,
        failed_incidents=failed,
        critical_count=critical,
        high_count=high,
        avg_confidence=round(avg_conf, 2),
    )


@app.get("/api/remediation-rules")
def get_remediation_rules():
    """Get all configured remediation rules."""
    return get_all_rules()


# ─── AlertManager Webhook ───

def _map_severity(alert_severity: str) -> Severity:
    """Map AlertManager severity label to our Severity enum."""
    mapping = {
        "critical": Severity.CRITICAL,
        "error": Severity.HIGH,
        "high": Severity.HIGH,
        "warning": Severity.MEDIUM,
        "info": Severity.LOW,
        "none": Severity.LOW,
    }
    return mapping.get(alert_severity.lower(), Severity.MEDIUM)


async def _run_rca_for_incident(incident_id: int):
    """Background task: run RCA via LLM for a new incident."""
    try:
        mcp_client = K8sMCPClient()
        llm_service = LLMService()
        pipeline = IncidentPipeline(mcp_client, llm_service)

        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == incident_id).first()
            if not incident:
                alert_logger.error(f"Incident {incident_id} not found for RCA")
                return

            await mcp_client.connect()

            # Gather cluster context for RCA
            cluster_context = {}
            try:
                cluster_context = await mcp_client.get_cluster_health()
            except Exception as e:
                alert_logger.warning(f"Could not gather cluster context: {e}")

            # Build incident data for LLM
            incident_data = {
                "title": incident.title,
                "severity": incident.severity.value if incident.severity else "medium",
                "namespace": incident.namespace,
                "resource_type": incident.resource_type,
                "resource_name": incident.resource_name,
                "description": incident.description,
            }

            # Get pod details if available
            if incident.resource_name and incident.resource_type == "Pod":
                try:
                    pod_desc = await mcp_client.describe_pod(
                        incident.resource_name, incident.namespace or "default"
                    )
                    incident_data["pod_description"] = pod_desc
                except Exception:
                    pass
                try:
                    pod_logs = await mcp_client.get_pod_logs(
                        incident.resource_name, incident.namespace or "default"
                    )
                    incident_data["pod_logs"] = pod_logs[:5000]
                except Exception:
                    pass

            # Generate RCA
            rca_result = await llm_service.generate_rca(incident_data, cluster_context)

            if rca_result:
                rca_report = RCAReport(
                    incident_id=incident.id,
                    root_cause=rca_result.root_cause,
                    analysis=rca_result.analysis,
                    recommendations=rca_result.recommendations,
                    confidence_score=rca_result.confidence_score,
                    llm_model=settings.bedrock_model_id,
                )
                db.add(rca_report)
                incident.status = IncidentStatus.ANALYZING
                db.commit()
                alert_logger.info(f"✅ RCA generated for incident #{incident.id}")

            await mcp_client.disconnect()
        finally:
            db.close()
    except Exception as e:
        alert_logger.error(f"❌ RCA generation failed for incident #{incident_id}: {e}")


@app.post("/api/webhook/alertmanager")
async def alertmanager_webhook(payload: AlertManagerPayload):
    """
    Receive alerts from Prometheus AlertManager.

    Configure AlertManager to send webhooks here:
        receivers:
          - name: 'k8s-agent'
            webhook_configs:
              - url: 'http://<agent-host>:8000/api/webhook/alertmanager'
    """
    alert_logger.info(f"📨 Received {len(payload.alerts)} alert(s) — status: {payload.status}")

    db = SessionLocal()
    created_incidents = []
    resolved_count = 0

    try:
        for alert in payload.alerts:
            fingerprint = alert.fingerprint
            alert_name = alert.labels.alertname
            namespace = alert.labels.namespace or "default"
            pod_name = alert.labels.pod
            severity = _map_severity(alert.labels.severity)

            if alert.status == "resolved":
                # Auto-resolve matching incidents
                existing = db.query(Incident).filter(
                    Incident.alert_fingerprint == fingerprint,
                    Incident.status.notin_([IncidentStatus.RESOLVED, IncidentStatus.FAILED]),
                ).all()
                for inc in existing:
                    inc.status = IncidentStatus.RESOLVED
                    inc.resolved_at = datetime.now(timezone.utc)
                    resolved_count += 1
                db.commit()
                continue

            # Check for duplicate (same fingerprint still active)
            existing = db.query(Incident).filter(
                Incident.alert_fingerprint == fingerprint,
                Incident.status.notin_([IncidentStatus.RESOLVED, IncidentStatus.FAILED]),
            ).first()
            if existing:
                alert_logger.info(f"⏭️ Skipping duplicate alert: {alert_name} ({fingerprint[:8]})")
                continue

            # Create new incident from alert
            title = alert.annotations.summary or f"[{alert_name}] {alert.annotations.description[:100]}" or alert_name
            description = alert.annotations.description or f"Alert {alert_name} fired"

            incident = Incident(
                title=title,
                description=description,
                severity=severity,
                namespace=namespace,
                resource_type="Pod" if pod_name else "Cluster",
                resource_name=pod_name or alert.labels.instance or "",
                status=IncidentStatus.DETECTED,
                source="alertmanager",
                alert_fingerprint=fingerprint,
                raw_data={
                    "alertname": alert_name,
                    "labels": alert.labels.model_dump(),
                    "annotations": alert.annotations.model_dump(),
                    "startsAt": alert.startsAt,
                    "generatorURL": alert.generatorURL,
                },
            )
            db.add(incident)
            db.flush()  # Get the ID

            alert_logger.info(f"🆕 Incident #{incident.id} created: {title}")
            created_incidents.append(incident.id)

        db.commit()
    finally:
        db.close()

    # Kick off async RCA for each new incident
    for inc_id in created_incidents:
        asyncio.create_task(_run_rca_for_incident(inc_id))

    return {
        "status": "accepted",
        "incidents_created": len(created_incidents),
        "incidents_resolved": resolved_count,
        "incident_ids": created_incidents,
    }


# ─── Dashboard Page ───

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the web dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})
