#!/bin/bash
# Start wda-mcp HTTP mode (OAuth + Bearer) detached from the current shell.
# Reads .env for WDA_TAILSCALE_IP / WDA_DEVICE_ID / WDA_BUNDLE_ID, and
# ~/.wda-oauth.json for the Bearer access token. Refuses to start without a token.
#
# Usage:
#   bash scripts/start_http.sh                         # default :8200
#   bash scripts/start_http.sh --port 9000             # custom port
#   bash scripts/start_http.sh --host 127.0.0.1        # bind to loopback only
#   bash scripts/start_http.sh --foreground            # foreground for debugging
#
# Env equivalents: WDA_HTTP_PORT, WDA_HTTP_HOST.

set -e

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-/opt/homebrew/bin/python3.12}"
LOG="${WDA_HTTP_LOG:-/tmp/wda_mcp_http.log}"
PID_FILE="${WDA_HTTP_PID_FILE:-/tmp/wda_mcp_http.pid}"

FOREGROUND=0
while [ $# -gt 0 ]; do
    case "$1" in
        --port) export WDA_HTTP_PORT="$2"; shift 2 ;;
        --host) export WDA_HTTP_HOST="$2"; shift 2 ;;
        --foreground) FOREGROUND=1; shift ;;
        *) echo "Unknown arg: $1"; exit 2 ;;
    esac
done

PORT="${WDA_HTTP_PORT:-8200}"
HOST="${WDA_HTTP_HOST:-0.0.0.0}"

if [ ! -f "$HOME/.wda-oauth.json" ] && [ -z "$WDA_OAUTH_ACCESS_TOKEN" ]; then
    echo "ERROR: ~/.wda-oauth.json missing. Run: python scripts/generate_oauth_creds.py"
    exit 1
fi

# Stop any prior instance bound to the target port
PRIOR=$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)
if [ -n "$PRIOR" ]; then
    echo "Stopping prior process on :$PORT (PIDs: $PRIOR)"
    kill $PRIOR 2>/dev/null || true
    sleep 2
fi

if [ "$FOREGROUND" = "1" ]; then
    exec "$PYTHON" server.py --http
fi

nohup "$PYTHON" server.py --http > "$LOG" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"
disown
sleep 2

if ! kill -0 "$PID" 2>/dev/null; then
    echo "ERROR: server exited within 2s. Last log lines:"
    tail -20 "$LOG"
    exit 1
fi

echo "wda-mcp HTTP started on http://$HOST:$PORT/mcp (PID $PID, log $LOG)"
echo "Tail with: tail -f $LOG"
