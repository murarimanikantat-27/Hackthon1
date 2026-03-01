"""
FastAPI application — REST API + web dashboard for incident management.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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
        rca_reports=[
            RCADetail(
                id=r.id,
                root_cause=r.root_cause,
                analysis=r.analysis,
                recommendations=r.recommendations,
                confidence_score=r.confidence_score or 0.0,
                llm_model=r.llm_model,
                created_at=r.created_at,
            )
            for r in incident.rca_reports
        ],
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
        )

        action = await pipeline.execute_remediation(incident, rca_result, db, manual_approval=True)

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
        await mcp_client.disconnect()


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
