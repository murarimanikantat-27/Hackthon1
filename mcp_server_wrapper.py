"""
Helper script to start the kubectl-mcp-server for stdio transport.
This runs as a separate subprocess, spawned by mcp_client.py.

Key: We import kubectl_mcp_tool.mcp_server (which sets
WindowsSelectorEventLoopPolicy), then override it back to
DefaultEventLoopPolicy so asyncio.run() works with subprocesses
on Python 3.13+ Windows.
"""
import sys
import os
import logging
import platform

# Suppress stdout logging — MCP stdio protocol owns stdout
logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stderr)],
)
for handler in logging.root.handlers[:]:
    if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
        logging.root.removeHandler(handler)

# Import the MCP server (this sets WindowsSelectorEventLoopPolicy on Windows)
from kubectl_mcp_tool.mcp_server import MCPServer

# Override back to DefaultEventLoopPolicy (ProactorEventLoop) which
# supports subprocesses on Windows with Python 3.13+
import asyncio
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


def main():
    server = MCPServer(name="kubernetes")
    try:
        asyncio.run(server.serve_stdio())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
