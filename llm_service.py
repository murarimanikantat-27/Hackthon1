"""
LLM Service — Uses AWS Bedrock Claude Sonnet 4.5 for generating
root cause analysis (RCA) from Kubernetes incident data.
"""

import json
import re
import logging
from typing import Any, Dict, List, Optional

import boto3
from pydantic import BaseModel, Field

from config import settings

logger = logging.getLogger(__name__)


# ─── Response Models ───

class RCAResult(BaseModel):
    """Structured RCA output from the LLM."""
    root_cause: str = Field(description="Primary root cause of the incident")
    analysis: str = Field(description="Detailed analysis explaining the issue")
    severity_assessment: str = Field(description="Critical / High / Medium / Low")
    recommendations: List[str] = Field(description="Ordered list of recommended actions")
    confidence_score: float = Field(description="Confidence in the analysis, 0.0 to 1.0")
    affected_components: List[str] = Field(description="List of affected Kubernetes resources")
    estimated_impact: str = Field(description="Impact assessment on the system")
    remediation_command: str = Field(default="", description="Exact kubectl command to remediate the issue")
    remediation_risk: str = Field(default="medium", description="Risk level of running the command: low/medium/high")
    remediation_explanation: str = Field(default="", description="Why this command will fix the issue")
    
    # New highly-structured RCA format fields
    executive_summary: str = Field(default="", description="Executive Summary")
    incident_detection: str = Field(default="", description="Incident Detection details")
    incident_timeline: List[str] = Field(default_factory=list, description="Incident Timeline")
    impact_assessment: str = Field(default="", description="Impact Assessment")
    resolution_actions: str = Field(default="", description="Resolution Actions")
    preventive_measures: str = Field(default="", description="Preventive Measures")
    lessons_learned: str = Field(default="", description="Lessons Learned")
    final_summary: str = Field(default="", description="Final Summary")


# ─── System Prompt ───

SYSTEM_PROMPT = """You are an expert Kubernetes Site Reliability Engineer (SRE) with deep expertise in:
- Kubernetes architecture, pod lifecycle, and networking
- Container runtime troubleshooting (Docker, containerd)
- Application performance debugging
- Infrastructure and cloud-native best practices

Your role is to analyze Kubernetes incidents and generate comprehensive Root Cause Analysis (RCA) reports.

When analyzing an incident, you must:
1. Identify the PRIMARY root cause (not just symptoms)
2. Trace the chain of events that led to the issue
3. Assess the severity and blast radius
4. Provide specific, actionable recommendations
5. Suggest both immediate fixes and long-term preventive measures
6. GENERATE THE EXACT kubectl REMEDIATION COMMAND to fix this specific issue based on cluster context

For the remediation_command field:
- Provide the exact kubectl command (without the 'kubectl' prefix) that will fix THIS specific issue
- Use the ACTUAL pod names, deployment names, namespaces from the cluster context
- Examples: "delete pod my-app-abc123 -n production", "rollout restart deployment/my-app -n default"
- If the issue requires a config change (like increasing memory), provide the exact command (e.g., "set resources deployment my-app -c=my-app --limits=memory=512Mi")
- YOU MUST ALWAYS PROVIDE A REMEDIATION COMMAND. Never leave it empty. Even if the fix is risky, provide the command and mark the risk level as 'high'.
- Assess the risk level: low (safe restart), medium (service disruption), high (data risk or breaking change)

IMPORTANT: Always respond with valid JSON matching this exact schema:
{
    "executive_summary": "string — high-level summary of what happened, root cause, and business impact",
    "incident_detection": "string — how it was detected and trigger signals",
    "incident_timeline": ["list of strings formatted as 'HH:MM:SS UTC - Event description'"],
    "impact_assessment": "string — business and user impact assessment",
    "resolution_actions": "string — what automated/manual actions were or will be taken",
    "preventive_measures": "string — immediate, short, and long-term measures",
    "lessons_learned": "string — what went well, what needs improvement",
    "final_summary": "string — closing summary of the incident",

    "root_cause": "string — clear one-line root cause",
    "analysis": "string — detailed technical analysis (can be same as root_cause_analysis)",
    "severity_assessment": "Critical | High | Medium | Low",
    "recommendations": ["ordered list of recommendations"],
    "confidence_score": 0.0 to 1.0,
    "affected_components": ["list of affected k8s resources"],
    "estimated_impact": "string — short impact description (or leave empty if using impact_assessment)",
    "remediation_command": "exact kubectl command to fix the issue (without kubectl prefix)",
    "remediation_risk": "low | medium | high",
    "remediation_explanation": "brief explanation of why this command will fix the issue"
}

Do NOT include any text outside the JSON object. Return ONLY valid JSON."""


class LLMService:
    """Service for generating RCA using AWS Bedrock Claude Sonnet 4.5."""

    def __init__(self):
        kwargs = {"region_name": settings.aws_region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self.client = boto3.client("bedrock-runtime", **kwargs)
        self.model_id = settings.bedrock_model_id
        logger.info(f"LLM Service initialized with model: {self.model_id}")

    def generate_rca(
        self,
        incident_title: str,
        incident_description: str,
        cluster_context: Dict[str, Any],
        additional_context: Optional[str] = None,
    ) -> RCAResult:
        """
        Generate a Root Cause Analysis for a Kubernetes incident.

        Args:
            incident_title: Short title of the incident
            incident_description: Description of what happened
            cluster_context: Raw data from MCP (pods, events, logs, etc.)
            additional_context: Optional extra context (pod describe, logs)

        Returns:
            RCAResult with structured analysis
        """
        # Build the user message with all context
        user_message = self._build_prompt(
            incident_title, incident_description, cluster_context, additional_context
        )

        logger.info(f"Sending RCA request to Bedrock for: {incident_title}")

        try:
            # Call AWS Bedrock
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "temperature": 0.2,
                    "system": SYSTEM_PROMPT,
                    "messages": [
                        {
                            "role": "user",
                            "content": user_message,
                        }
                    ],
                }),
            )

            # Parse the response
            response_body = json.loads(response["body"].read())
            assistant_text = response_body["content"][0]["text"]

            logger.info("✅ Received RCA response from Bedrock.")
            logger.debug(f"Raw LLM response: {assistant_text}")

            # Strip markdown code block wrappers if present
            clean_text = assistant_text.strip()
            clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text)
            clean_text = re.sub(r'\s*```$', '', clean_text)
            clean_text = clean_text.strip()

            # Parse JSON response into structured model
            rca_data = json.loads(clean_text)
            return RCAResult(**rca_data)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.error(f"Raw response: {assistant_text}")
            # Return a fallback RCA
            return RCAResult(
                root_cause="Unable to parse LLM response",
                analysis=f"Raw LLM response:\n{assistant_text}",
                severity_assessment="Medium",
                recommendations=["Review the raw LLM output manually"],
                immediate_actions=["Check the incident manually"],
                preventive_measures=["Investigate LLM prompt quality"],
                confidence_score=0.1,
                affected_components=[],
                estimated_impact="Unknown — requires manual review",
            )
        except Exception as e:
            logger.error(f"Bedrock API call failed: {e}")
            raise

    def _build_prompt(
        self,
        title: str,
        description: str,
        cluster_context: Dict[str, Any],
        additional_context: Optional[str] = None,
    ) -> str:
        """Build a detailed prompt with all available context."""
        sections = [
            f"## Incident Report",
            f"**Title:** {title}",
            f"**Description:** {description}",
            "",
            "## Kubernetes Cluster Context",
        ]

        for key, value in cluster_context.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    sections.append(f"### {key} — {sub_key}")
                    sections.append(f"```\n{sub_value}\n```")
            else:
                sections.append(f"### {key}")
                sections.append(f"```\n{value}\n```")

        if additional_context:
            sections.append("")
            sections.append("## Additional Context")
            sections.append(additional_context)

        sections.append("")
        sections.append("## Instructions")
        sections.append("Analyze the above incident data and provide a comprehensive RCA in JSON format.")

        return "\n".join(sections)

    def test_connection(self) -> bool:
        """Test connectivity to Bedrock."""
        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Say OK"}],
                }),
            )
            body = json.loads(response["body"].read())
            logger.info(f"✅ Bedrock connection OK: {body['content'][0]['text']}")
            return True
        except Exception as e:
            logger.error(f"❌ Bedrock connection failed: {e}")
            return False
