"""ChatGPT-specific HTTP entrypoint for WDA-MCP.

Keep Claude/Codex stdio usage on server.py. Use this file when exposing WDA-MCP
as a remote MCP app for ChatGPT Developer Mode.
"""

import argparse
import os

from server import mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Run WDA-MCP for ChatGPT over streamable HTTP.")
    parser.add_argument("--host", default=os.environ.get("WDA_GPT_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WDA_GPT_PORT", "8200")))
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
