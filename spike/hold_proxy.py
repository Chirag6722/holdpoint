"""Spike: stdio MCP proxy that holds every tool labelled `commit`.

Usage: hold_proxy.py POLICY.json [--allow NAME] -- COMMAND [ARG...]

Fails closed: a tool missing from the policy is treated as `commit`.
"""
import json
import os
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
from fastmcp.server.server import create_proxy


class Hold(Middleware):
    def __init__(self, policy, allow):
        self.policy, self.allow = policy, allow

    async def on_call_tool(self, context, call_next):
        name = context.message.name
        if name not in self.allow and self.policy.get(name, "commit") == "commit":
            raise ToolError(f"HELD by gate: {name} did not run. Tell the user what you need confirmed.")
        return await call_next(context)


def main():
    argv = sys.argv[1:]
    split = argv.index("--")
    head, downstream = argv[:split], argv[split + 1:]
    with open(head[0], encoding="utf-8") as f:
        policy = json.load(f)
    allow = {head[i + 1] for i, a in enumerate(head) if a == "--allow"}
    transport = StdioTransport(downstream[0], downstream[1:], env=dict(os.environ), keep_alive=True)
    proxy = create_proxy(Client(transport), name="hold_proxy")
    proxy.add_middleware(Hold(policy, allow))
    proxy.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
