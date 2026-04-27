#!/bin/bash
# prep_for_chatgpt.sh — pre-flight everything you need before pasting a URL into
# ChatGPT (or any remote MCP client). Idempotent and safe to re-run.
#
# What this DOES:
#   1. Inventory: who's on the port, is cloudflared up, is there a matching ingress.
#   2. Generate ~/.wda-oauth.json if missing.
#   3. Start the wda-mcp HTTP server if the port is free.
#   4. Local self-check: curl http://127.0.0.1:<port>/mcp (loopback bypass).
#   5. Optional public-URL check (curl with and without Bearer).
#   6. Print connector URL, Bearer token, and ChatGPT header to paste.
#
# What this DOES NOT do (intentionally):
#   - Start or configure cloudflared / ngrok. Tunnel choice is identity-related
#     (which domain, which account); you decide. Output tells you what's needed.
#
# Usage:
#   bash scripts/prep_for_chatgpt.sh
#   bash scripts/prep_for_chatgpt.sh --port 9000
#   bash scripts/prep_for_chatgpt.sh --url https://wda-mcp.example.com/mcp
#   bash scripts/prep_for_chatgpt.sh --port 9000 --url https://your-host/mcp --regenerate
#
# Env equivalents: WDA_HTTP_PORT, WDA_HTTP_HOST.

set -e

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-/opt/homebrew/bin/python3.12}"
URL=""
REGENERATE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --port) export WDA_HTTP_PORT="$2"; shift 2 ;;
        --host) export WDA_HTTP_HOST="$2"; shift 2 ;;
        --url)  URL="$2"; shift 2 ;;
        --regenerate) REGENERATE=1; shift ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \?//' | head -30
            exit 0
            ;;
        *) echo "Unknown arg: $1"; exit 2 ;;
    esac
done

PORT="${WDA_HTTP_PORT:-8200}"
HOST="${WDA_HTTP_HOST:-0.0.0.0}"
CRED_FILE="$HOME/.wda-oauth.json"

hr() { echo "────────────────────────────────────────"; }
section() { echo; hr; echo "▶ $1"; hr; }

# ─── Step 1: Inventory ──────────────────────────────────────────
section "Step 1 / 6  Inventory"

PORT_OWNER=""
if PORT_PID=$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1); then
    if [ -n "$PORT_PID" ]; then
        PORT_OWNER=$(ps -p "$PORT_PID" -o command= 2>/dev/null || echo "unknown")
        echo "Port $PORT: in use (PID $PORT_PID)"
        echo "  command: $PORT_OWNER"
    fi
fi
[ -z "$PORT_OWNER" ] && echo "Port $PORT: free"

CF_PROC=$(pgrep -fl 'cloudflared tunnel run' 2>/dev/null || true)
if [ -n "$CF_PROC" ]; then
    echo "cloudflared: running"
    echo "  $CF_PROC"
else
    echo "cloudflared: not running"
fi

CF_CONFIG="$HOME/.cloudflared/config.yml"
MATCHED_HOST=""
if [ -f "$CF_CONFIG" ]; then
    # Find the hostname mapped to localhost:<port> in the ingress section.
    MATCHED_HOST=$("$PYTHON" - "$CF_CONFIG" "$PORT" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
port = sys.argv[2]
blocks = re.findall(
    r'-\s*hostname:\s*(\S+)\s*\n\s*service:\s*http://localhost:(\d+)',
    text,
)
for host, p in blocks:
    if p == port:
        print(host)
        break
PY
)
    if [ -n "$MATCHED_HOST" ]; then
        echo "cloudflared config: routes 'https://$MATCHED_HOST' → localhost:$PORT"
    else
        echo "cloudflared config: present but no ingress matches localhost:$PORT"
    fi
else
    echo "cloudflared config: ~/.cloudflared/config.yml not found"
fi

# ─── Step 2: OAuth credentials ──────────────────────────────────
section "Step 2 / 6  OAuth credentials"

if [ "$REGENERATE" = "1" ]; then
    "$PYTHON" scripts/generate_oauth_creds.py --force
elif [ ! -f "$CRED_FILE" ]; then
    "$PYTHON" scripts/generate_oauth_creds.py
else
    echo "$CRED_FILE exists (use --regenerate to rotate)"
fi

TOKEN=$("$PYTHON" -c "import json,pathlib; print(json.loads(pathlib.Path('$CRED_FILE').read_text())['access_token'])" 2>/dev/null) || {
    echo "ERROR: could not read access_token from $CRED_FILE"; exit 1;
}

# ─── Step 3: Start the server ───────────────────────────────────
section "Step 3 / 6  Start wda-mcp HTTP"

if [ -n "$PORT_OWNER" ]; then
    if echo "$PORT_OWNER" | grep -qE 'server\.py|server_chatgpt\.py'; then
        echo "wda-mcp already on port $PORT (PID $PORT_PID) — leaving it alone."
    else
        echo "ERROR: port $PORT is held by something other than wda-mcp:"
        echo "  $PORT_OWNER"
        echo "Stop it manually or pass --port to use a different port."
        exit 1
    fi
else
    bash scripts/start_http.sh --port "$PORT" --host "$HOST"
fi

# ─── Step 4: Local self-check ───────────────────────────────────
section "Step 4 / 6  Local self-check (loopback bypass)"

LOCAL_CODE="000"
for i in 1 2 3 4 5; do
    LOCAL_CODE=$(curl -sS -o /tmp/prep_local.txt -w "%{http_code}" --max-time 5 \
        -X POST "http://127.0.0.1:$PORT/mcp" \
        -H "Accept: application/json, text/event-stream" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"prep","version":"0"}}}' \
        2>/dev/null || echo "000")
    [ "$LOCAL_CODE" = "200" ] && break
    echo "  waiting for server to be ready… (attempt $i/5)"
    sleep 2
done

if [ "$LOCAL_CODE" = "200" ]; then
    echo "127.0.0.1:$PORT/mcp → HTTP 200 ✓ (server alive, MCP handshake OK)"
else
    echo "127.0.0.1:$PORT/mcp → HTTP $LOCAL_CODE ✗"
    echo "Body:"; head -c 300 /tmp/prep_local.txt; echo
    echo "Server may not be ready yet. Check tail -f /tmp/wda_mcp_http.log"
    exit 1
fi

# ─── Step 5: Public-URL check ───────────────────────────────────
section "Step 5 / 6  Public URL check"

if [ -z "$URL" ] && [ -n "$MATCHED_HOST" ]; then
    URL="https://$MATCHED_HOST/mcp"
    echo "(using URL inferred from cloudflared config: $URL)"
fi

if [ -n "$URL" ]; then
    NOAUTH=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 8 -X POST "$URL" \
        -H "Accept: application/json, text/event-stream" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"prep-noauth","version":"0"}}}' \
        2>/dev/null || echo "000")
    AUTH=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 8 -X POST "$URL" \
        -H "Accept: application/json, text/event-stream" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"prep","version":"0"}}}' \
        2>/dev/null || echo "000")
    echo "no-auth   → HTTP $NOAUTH  (want 401)"
    echo "with-auth → HTTP $AUTH    (want 200)"
    if [ "$NOAUTH" != "401" ] || [ "$AUTH" != "200" ]; then
        echo
        echo "Public URL not ready. Common causes:"
        echo "  502/522: tunnel up, origin down"
        echo "  404 (Cloudflare): tunnel hostname has no ingress to localhost:$PORT"
        echo "  DNS not propagated yet — wait ~30s and re-run"
        exit 1
    fi
else
    echo "Skipped — no public URL provided. Pass --url <https://host/mcp> to verify."
fi

# ─── Step 6: Summary ────────────────────────────────────────────
section "Step 6 / 6  Ready for ChatGPT"

cat <<EOF
Connector URL:
  ${URL:-<set up your tunnel, then re-run with --url to verify>}

Authorization header (paste into ChatGPT custom headers):
  Authorization: Bearer $TOKEN

If ChatGPT prefers OAuth instead of static Bearer, the server already exposes:
  /.well-known/oauth-protected-resource
  /.well-known/oauth-authorization-server
  /oauth/authorize
  /oauth/token

ChatGPT setup:
  Settings → Apps & Connectors → Developer mode → Create app
  → Connector URL = the URL above
  → Custom header = the Authorization line above
  → Confirm wda_check / wda_tap / wda_type appear

Server log: tail -f /tmp/wda_mcp_http.log
EOF
