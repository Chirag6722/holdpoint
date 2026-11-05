"""Raise the harnesses' 5-second MCP request limit, without editing their source.

A review can take longer than 5 seconds, which would look like a tool failure to
the agent. Baseline and gated runs both use this, so the conditions stay equal.
Benchmark sandbox tools answer immediately, so the limit does not affect them.
"""
import agent  # noqa: F401 - must load first; the benchmark's runtime modules import it circularly
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams

from src.runtime import googleadk, openaisdk

MCP_TIMEOUT_SECONDS = 120.0


class _SlowOpenAIServer(openaisdk._NameSafeMCPServer):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("client_session_timeout_seconds", MCP_TIMEOUT_SECONDS)
        super().__init__(*args, **kwargs)


class _SlowADKToolset(googleadk.RuntimeMcpToolset):
    def __init__(self, *args, connection_params, **kwargs):
        wrapped = StdioConnectionParams(server_params=connection_params, timeout=MCP_TIMEOUT_SECONDS)
        super().__init__(*args, connection_params=wrapped, **kwargs)


def apply():
    openaisdk._NameSafeMCPServer = _SlowOpenAIServer
    googleadk.RuntimeMcpToolset = _SlowADKToolset
