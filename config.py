"""
Configuration module — loads settings from .env file using pydantic-settings.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ─── AWS Bedrock ───
    aws_region: str = "ap-south-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    bedrock_model_id: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"

    # ─── PostgreSQL ───
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "password"
    db_name: str = "k8s_incident_hub"
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # ─── Kubernetes MCP Server ───
    k8s_mcp_server_command: str = "kubectl-mcp-server"
    k8s_mcp_server_args: str = "--transport stdio"

    # ─── Agent ───
    polling_interval_seconds: int = 60
    auto_remediate: bool = False
    monitor_duration_minutes: int = 5
    target_namespaces: str = "default"

    # ─── Email Alert Monitoring ───
    email_imap_server: str = ""        # e.g. imap.gmail.com
    email_imap_port: int = 993
    email_address: str = ""            # your email address
    email_password: str = ""           # email password or app password
    alert_sender_email: str = ""       # filter: only read emails from this sender (leave empty for all)
    email_poll_interval_seconds: int = 10

    # ─── Dashboard ───
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8000

    @property
    def namespace_list(self) -> List[str]:
        return [ns.strip() for ns in self.target_namespaces.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
