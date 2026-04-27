#!/bin/bash
# Watch the WiFi -> cellular handoff path.
# Usage: bash scripts/watch_handoff.sh <IPHONE_TAILSCALE_IP> [INTERVAL_SECONDS]

set -u

TAILSCALE_IP="${1:?Usage: $0 <IPHONE_TAILSCALE_IP> [INTERVAL_SECONDS]}"
INTERVAL="${2:-2}"

tcp_check() {
  python3.12 - "$1" "$2" >/dev/null 2>&1 <<'PY'
import socket
import sys

ip = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket()
s.settimeout(1.5)
s.connect((ip, port))
s.close()
PY
}

echo "Watching iPhone handoff via Tailscale IP: $TAILSCALE_IP"
echo "Columns: time | tailscale ping | WDA 8100 | RemotePairing 49152"
echo "Switch WiFi/cellular now, then stop with Ctrl+C."
echo ""

while true; do
  now="$(date '+%H:%M:%S')"

  if command -v tailscale >/dev/null 2>&1 && tailscale ping -c 1 "$TAILSCALE_IP" >/tmp/wda_handoff_ping.txt 2>/dev/null; then
    ping_status="$(sed -n '1p' /tmp/wda_handoff_ping.txt | sed 's/[[:space:]]\\+/ /g')"
  else
    ping_status="FAIL"
  fi

  if curl -m 2 -fsS "http://$TAILSCALE_IP:8100/status" >/dev/null 2>&1; then
    wda_status="OK"
  else
    wda_status="FAIL"
  fi

  if tcp_check "$TAILSCALE_IP" 49152; then
    rp_status="OK"
  else
    rp_status="FAIL"
  fi

  printf '%s | ping=%s | 8100=%s | 49152=%s\n' "$now" "$ping_status" "$wda_status" "$rp_status"
  sleep "$INTERVAL"
done
