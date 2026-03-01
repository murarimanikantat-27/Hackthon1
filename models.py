"""
SQLAlchemy models for Incident, RCA Report, and Remediation Action.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Enum, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from database import Base


# ─── Enums ───

class IncidentStatus(str, enum.Enum):
    DETECTED = "detected"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    REMEDIATING = "remediating"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    FAILED = "failed"


class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RemediationStatus(str, enum.Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# ─── Models ───

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    severity = Column(Enum(Severity), default=Severity.MEDIUM)
    namespace = Column(String(255), default="default")
    resource_type = Column(String(100))  # pod, deployment, node, etc.
    resource_name = Column(String(500))
    description = Column(Text)
    raw_data = Column(JSON)  # raw cluster data from MCP
    status = Column(Enum(IncidentStatus), default=IncidentStatus.DETECTED)
    source = Column(String(50), default="mcp-poll")  # "mcp-poll" or "alertmanager"
    alert_fingerprint = Column(String(255), nullable=True, index=True)  # AlertManager dedup key
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    rca_reports = relationship("RCAReport", back_populates="incident", cascade="all, delete-orphan")
    remediation_actions = relationship("RemediationAction", back_populates="incident", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Incident(id={self.id}, title='{self.title}', status={self.status})>"


class RCAReport(Base):
    __tablename__ = "rca_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    root_cause = Column(Text, nullable=False)
    analysis = Column(Text)
    recommendations = Column(JSON)  # list of recommended actions
    confidence_score = Column(Float, default=0.0)  # 0.0 to 1.0
    llm_model = Column(String(200))
    raw_response = Column(Text)  # full LLM response for debugging
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    incident = relationship("Incident", back_populates="rca_reports")

    def __repr__(self):
        return f"<RCAReport(id={self.id}, incident_id={self.incident_id}, confidence={self.confidence_score})>"


class RemediationAction(Base):
    __tablename__ = "remediation_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    action_type = Column(String(100))  # restart_pod, rollout_restart, scale, etc.
    command = Column(Text)  # the actual kubectl command or MCP tool call
    result = Column(Text)  # output from the command
    status = Column(Enum(RemediationStatus), default=RemediationStatus.PENDING)
    executed_at = Column(DateTime, nullable=True)

    # Relationships
    incident = relationship("Incident", back_populates="remediation_actions")

    def __repr__(self):
        return f"<RemediationAction(id={self.id}, action_type='{self.action_type}', status={self.status})>"
