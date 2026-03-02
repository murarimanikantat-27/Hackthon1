"""
MCP Client — connects to kubectl-mcp-server via stdio transport
to query Kubernetes cluster state and execute remediation commands.

Uses the kubectl_mcp_tool package's MCPServer + FastMCP directly
via stdio subprocess to avoid event loop conflicts on Windows.
"""

import asyncio
import json
import logging
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import settings

logger = logging.getLogger(__name__)


def _resolve_mcp_command() -> tuple:
    """
    Resolve the MCP server command for stdio subprocess.
    Uses our wrapper script which handles Windows event loop policy.
    """
    wrapper_path = Path(__file__).parent / "mcp_server_wrapper.py"
    return sys.executable, [str(wrapper_path)]


class K8sMCPClient:
    """Client that communicates with a Kubernetes MCP server."""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._exit_stack = AsyncExitStack()
        self._connected = False

    async def connect(self):
        """Start the MCP server subprocess and initialize the session."""
        if self._connected:
            logger.info("Already connected to MCP server.")
            return

        command, args = _resolve_mcp_command()

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env={
                **os.environ,
                # Ensure the subprocess also uses the selector event loop on Windows
                "PYTHONPATH": os.pathsep.join(sys.path),
            },
        )

        logger.info(f"Starting MCP server: {command} {' '.join(args)}")

        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        await self.session.initialize()
        self._connected = True
        logger.info("✅ Connected to Kubernetes MCP server.")

    async def disconnect(self):
        """Shut down the MCP server subprocess."""
        if self._connected:
            await self._exit_stack.aclose()
            self._connected = False
            logger.info("🔌 Disconnected from MCP server.")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools exposed by the MCP server."""
        if not self.session:
            raise RuntimeError("Not connected. Call connect() first.")

        result = await self.session.list_tools()
        tools = []
        for tool in result.tools:
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
            })
        return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> str:
        """Call a specific MCP tool and return the text result."""
        if not self.session:
            raise RuntimeError("Not connected. Call connect() first.")

        logger.info(f"🔧 Calling MCP tool: {tool_name} with args: {arguments}")
        result = await self.session.call_tool(tool_name, arguments or {})

        # Extract text content from the result
        text_parts = []
        for content in result.content:
            if hasattr(content, 'text'):
                text_parts.append(content.text)
        return "\n".join(text_parts)

    # ─── Convenience Methods ───

    async def get_pods(self, namespace: str = "default") -> str:
        """Get all pods in a namespace."""
        return await self.call_tool("get_pods", {"namespace": namespace})

    async def get_pod_logs(self, pod_name: str, namespace: str = "default", tail_lines: int = 100) -> str:
        """Get logs from a specific pod."""
        return await self.call_tool("get_pod_logs", {
            "pod_name": pod_name,
            "namespace": namespace,
            "tail_lines": tail_lines,
        })

    async def describe_pod(self, pod_name: str, namespace: str = "default") -> str:
        """Get detailed description of a pod."""
        return await self.call_tool("describe_pod", {
            "pod_name": pod_name,
            "namespace": namespace,
        })

    async def get_events(self, namespace: str = "default") -> str:
        """Get events in a namespace."""
        return await self.call_tool("get_events", {"namespace": namespace})

    async def get_nodes(self) -> str:
        """Get cluster node status."""
        return await self.call_tool("get_nodes", {})

    async def get_deployments(self, namespace: str = "default") -> str:
        """Get deployments in a namespace."""
        return await self.call_tool("get_deployments", {"namespace": namespace})

    async def run_kubectl(self, command: str) -> str:
        """Run an arbitrary kubectl command via MCP."""
        return await self.call_tool("run_kubectl", {"command": command})

    async def get_cluster_health(self) -> Dict[str, Any]:
        """Gather comprehensive cluster health data from multiple sources."""
        health_data = {}

        for namespace in settings.namespace_list:
            ns_data = {}
            try:
                ns_data["pods"] = await self.get_pods(namespace)
            except Exception as e:
                ns_data["pods"] = f"Error: {e}"
                logger.warning(f"Failed to get pods in {namespace}: {e}")

            try:
                ns_data["events"] = await self.get_events(namespace)
            except Exception as e:
                ns_data["events"] = f"Error: {e}"
                logger.warning(f"Failed to get events in {namespace}: {e}")

            try:
                ns_data["deployments"] = await self.get_deployments(namespace)
            except Exception as e:
                ns_data["deployments"] = f"Error: {e}"
                logger.warning(f"Failed to get deployments in {namespace}: {e}")

            health_data[namespace] = ns_data

        try:
            health_data["nodes"] = await self.get_nodes()
        except Exception as e:
            health_data["nodes"] = f"Error: {e}"
            logger.warning(f"Failed to get nodes: {e}")

        return health_data

    async def get_failing_pods(self, namespace: str = "default") -> str:
        """Query for pods in error states (CrashLoopBackOff, Error, ImagePullBackOff)."""
        try:
            # Use kubectl to filter for non-running pods
            result = await self.run_kubectl(
                f"get pods -n {namespace} --field-selector=status.phase!=Running,status.phase!=Succeeded -o json"
            )
            return result
        except Exception as e:
            logger.warning(f"Failed to get failing pods, falling back to all pods: {e}")
            return await self.get_pods(namespace)

    async def execute_remediation_command(self, command: str) -> str:
        """Execute a remediation kubectl command."""
        logger.info(f"⚡ Executing remediation: {command}")
        
        try:
            exec_cmd = command[8:] if command.startswith("kubectl ") else command
            tool_output = await self.run_kubectl(exec_cmd)
            if "Unknown tool" in tool_output or "unrecognized tool" in tool_output.lower():
                raise ValueError("Unknown tool")
            return tool_output
        except Exception as e:
            error_str = str(e)
            if "Unknown tool" in error_str or isinstance(e, ValueError):
                import subprocess
                import os
                logger.info(f"  MCP tool 'run_kubectl' missing. Falling back to subprocess for: {command}")
                safe_cmd = command if command.startswith("kubectl") else f"kubectl {command}"
                process = subprocess.run(
                    safe_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    shell=True,
                    env=os.environ.copy()
                )
                if process.returncode == 0:
                    return process.stdout
                else:
                    raise Exception(f"Subprocess failed: {process.stderr}")
            raise e

    async def test_connection(self):
        """Test connectivity to the MCP server."""
        try:
            await self.connect()
            tools = await self.list_tools()
            print(f"✅ Connected! Available tools ({len(tools)}):")
            for tool in tools:
                print(f"  • {tool['name']}: {tool['description']}")
            await self.disconnect()
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            raise
