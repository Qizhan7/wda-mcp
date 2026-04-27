"""ChatGPT-specific HTTP entrypoint for WDA-MCP.

Keep Claude/Codex stdio usage on `server.py`. Use this file when exposing WDA-MCP
as a remote MCP app for ChatGPT Developer Mode. Both entry points share the same
OAuth + Bearer auth runner; this one just forwards host/port arguments.
"""

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Run WDA-MCP for ChatGPT over streamable HTTP with OAuth.")
    parser.add_argument("--host", default=os.environ.get("WDA_GPT_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WDA_GPT_PORT", "8200")))
    args = parser.parse_args()

    os.environ["WDA_HTTP_HOST"] = args.host
    os.environ["WDA_HTTP_PORT"] = str(args.port)

    from server import _run_http
    _run_http()


if __name__ == "__main__":
    main()
