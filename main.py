"""
Main entrypoint — CLI for the Kubernetes Incident Management Agent.
Supports three modes: agent (polling loop), server (dashboard), or both.
"""

import argparse
import asyncio
import logging
import platform
import signal
import sys
from contextlib import asynccontextmanager

# Windows requires SelectorEventLoopPolicy for subprocess pipe transport
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

from config import settings
from database import init_db
from mcp_client import K8sMCPClient
from llm_service import LLMService
from incident_pipeline import IncidentPipeline

# ─── Logging Setup ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)-20s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("k8s-agent")

# Graceful shutdown flag
_shutdown = asyncio.Event()


def handle_signal(sig, frame):
    logger.info(f"Received signal {sig}. Shutting down gracefully...")
    _shutdown.set()


async def run_agent(dry_run: bool = False):
    """Run the agent polling loop."""
    logger.info("🤖 Starting Kubernetes Incident Agent...")
    logger.info(f"   Polling interval: {settings.polling_interval_seconds}s")
    logger.info(f"   Target namespaces: {settings.namespace_list}")
    logger.info(f"   Auto-remediate: {settings.auto_remediate}")
    logger.info(f"   LLM Model: {settings.bedrock_model_id}")

    # Initialize components
    mcp_client = K8sMCPClient()
    llm_service = LLMService()
    pipeline = IncidentPipeline(mcp_client, llm_service)

    try:
        # Connect to MCP server
        await mcp_client.connect()
        tools = await mcp_client.list_tools()
        logger.info(f"   MCP tools available: {len(tools)}")

        # Main polling loop
        cycle_count = 0
        while not _shutdown.is_set():
            cycle_count += 1
            logger.info(f"\n{'─' * 60}")
            logger.info(f"📡 Cycle #{cycle_count}")
            logger.info(f"{'─' * 60}")

            try:
                await pipeline.run_cycle(dry_run=dry_run)
            except Exception as e:
                logger.error(f"Cycle #{cycle_count} failed: {e}", exc_info=True)

            # Wait for next cycle or shutdown
            try:
                await asyncio.wait_for(
                    _shutdown.wait(),
                    timeout=settings.polling_interval_seconds,
                )
                break  # shutdown signaled
            except asyncio.TimeoutError:
                pass  # continue to next cycle

    finally:
        await mcp_client.disconnect()
        logger.info("🛑 Agent stopped.")


async def run_server():
    """Start the FastAPI dashboard server."""
    from api import app

    config = uvicorn.Config(
        app,
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_email_monitor():
    """Run the email alert monitor loop."""
    from email_monitor import EmailAlertMonitor
    monitor = EmailAlertMonitor()
    await monitor.run_loop(_shutdown)


async def run_both(dry_run: bool = False):
    """Run agent and server concurrently."""
    await asyncio.gather(
        run_agent(dry_run=dry_run),
        run_server(),
    )


async def run_email_and_server():
    """Run email monitor + dashboard server."""
    await asyncio.gather(
        run_email_monitor(),
        run_server(),
    )


async def run_all(dry_run: bool = False):
    """Run email monitor + MCP agent + dashboard server."""
    await asyncio.gather(
        run_email_monitor(),
        run_agent(dry_run=dry_run),
        run_server(),
    )


def main():
    parser = argparse.ArgumentParser(
        description="🤖 Kubernetes Incident Management Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode email               # Email monitor + dashboard
  python main.py --mode agent               # MCP polling agent + dashboard
  python main.py --mode both                # MCP agent + dashboard
  python main.py --mode all                 # Email + MCP agent + dashboard
  python main.py --mode server              # Dashboard only
  python main.py --mode agent --dry-run     # Detect & analyze without remediation
  python main.py --test-mcp                # Test MCP server connectivity
  python main.py --test-llm                # Test Bedrock connectivity
  python main.py --init-db                 # Initialize database tables
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["agent", "server", "both", "email", "all"],
        default="email",
        help="Run mode: email (email monitor + dashboard), agent (MCP polling), both (agent + dashboard), all (email + agent + dashboard), server (dashboard only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run detection and analysis without executing remediation.",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize the database tables and exit.",
    )
    parser.add_argument(
        "--test-mcp",
        action="store_true",
        help="Test MCP server connectivity and exit.",
    )
    parser.add_argument(
        "--test-llm",
        action="store_true",
        help="Test AWS Bedrock connectivity and exit.",
    )

    args = parser.parse_args()

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # ─── Quick actions ───
    if args.init_db:
        init_db()
        return

    if args.test_mcp:
        async def _test():
            client = K8sMCPClient()
            await client.test_connection()
        asyncio.run(_test())
        return

    if args.test_llm:
        llm = LLMService()
        llm.test_connection()
        return

    # ─── Initialize DB ───
    logger.info("📦 Initializing database...")
    init_db()

    # ─── Run selected mode ───
    logger.info(f"🚀 Starting in '{args.mode}' mode...")

    if args.mode == "email":
        asyncio.run(run_email_and_server())
    elif args.mode == "agent":
        asyncio.run(run_agent(dry_run=args.dry_run))
    elif args.mode == "server":
        asyncio.run(run_server())
    elif args.mode == "both":
        asyncio.run(run_both(dry_run=args.dry_run))
    elif args.mode == "all":
        asyncio.run(run_all(dry_run=args.dry_run))


if __name__ == "__main__":
    main()

