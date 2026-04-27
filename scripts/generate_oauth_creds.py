#!/usr/bin/env python3
"""Generate OAuth credentials for wda-mcp HTTP mode.

Writes ~/.wda-oauth.json (chmod 600) with random client_id, client_secret, and
access_token. The HTTP server reads this file at startup; the access_token is
also what MCP clients send in the Authorization: Bearer header.
"""

import argparse
import json
import os
import pathlib
import secrets
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Overwrite existing credentials")
    parser.add_argument("--path", default=str(pathlib.Path.home() / ".wda-oauth.json"))
    args = parser.parse_args()

    cred_path = pathlib.Path(args.path)
    if cred_path.exists() and not args.force:
        print(f"Refusing to overwrite existing {cred_path}. Pass --force to regenerate.", file=sys.stderr)
        sys.exit(1)

    creds = {
        "client_id": secrets.token_urlsafe(16),
        "client_secret": secrets.token_urlsafe(32),
        "access_token": secrets.token_urlsafe(32),
    }

    cred_path.write_text(json.dumps(creds, indent=2))
    os.chmod(cred_path, 0o600)

    print(f"Wrote {cred_path} (chmod 600)")
    print()
    print("Use this Bearer token in Claude.ai / ChatGPT MCP connector or curl:")
    print(f"  Authorization: Bearer {creds['access_token']}")
    print()
    print("OAuth client_credentials flow (for clients that need it):")
    print(f"  client_id     = {creds['client_id']}")
    print(f"  client_secret = {creds['client_secret']}")


if __name__ == "__main__":
    main()
