#!/bin/bash
# Diagnose the USB -> WiFi/Tailscale handoff.
# Usage: bash scripts/diagnose_usb_wifi.sh [IPHONE_WIFI_IP] [IPHONE_TAILSCALE_IP]

set -u

WIFI_IP="${1:-}"
TAILSCALE_IP="${2:-}"
OK=0
FAIL=0
WARN=0

pass() {
  echo "  [OK] $1"
  OK=$((OK + 1))
}

fail() {
  echo "  [FAIL] $1"
  echo "     $2"
  FAIL=$((FAIL + 1))
}

warn() {
  echo "  [WARN] $1"
  echo "     $2"
  WARN=$((WARN + 1))
}

check_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    pass "$2"
  else
    fail "$2" "$3"
  fi
}

check_http_status() {
  local label="$1"
  local ip="$2"
  local url="http://$ip:8100/status"
  if curl -m 3 -fsS "$url" >/tmp/wda_status_check.json 2>/tmp/wda_status_check.err; then
    pass "$label WDA status: $url"
  else
    fail "$label WDA status failed: $url" "WDA may not be running, the IP may be wrong, or port 8100 is blocked. If ping works but this fails, check the iPhone automation screen and /tmp/wda_run.log."
  fi
}

check_tcp_port() {
  local label="$1"
  local ip="$2"
  local port="$3"
  local help="$4"
  if python3.12 - "$ip" "$port" >/dev/null 2>&1 <<'PY'
import socket
import sys

ip = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket()
s.settimeout(3)
s.connect((ip, port))
s.close()
PY
  then
    pass "$label port $port open"
  else
    fail "$label port $port closed/unreachable" "$help"
  fi
}

print_mac_network_snapshot() {
  echo ""
  echo "Mac network snapshot:"
  if command -v route >/dev/null 2>&1; then
    echo "Default route:"
    route -n get default 2>/dev/null | awk '/gateway:|interface:|source address:/ { print "  " $0 }' || true
  fi
  if command -v networksetup >/dev/null 2>&1; then
    echo "WiFi SSID by interface:"
    for iface in en0 en1 en2; do
      ssid="$(networksetup -getairportnetwork "$iface" 2>/dev/null || true)"
      case "$ssid" in
        *"You are not associated"*|*"not a Wi-Fi interface"*|*"Error obtaining wireless information"*|"") ;;
        *) echo "  $iface: $ssid" ;;
      esac
    done
    echo "Network service order:"
    networksetup -listnetworkserviceorder 2>/dev/null | sed -n '1,18p' | sed 's/^/  /' || true
  fi
}

echo "=== USB -> WiFi/Tailscale Handoff Diagnosis ==="
echo ""

check_cmd "python3.12" "Python 3.12 available" "Install Python 3.12, then install mcp/pymobiledevice3 as documented."
check_cmd "curl" "curl available" "curl is required for HTTP status checks."

if command -v ipconfig >/dev/null 2>&1; then
  echo ""
  echo "Mac local IPs:"
  for iface in en0 en1 en2; do
    ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    [ -n "$ip" ] && echo "  $iface: $ip"
  done
fi

print_mac_network_snapshot

if [ -n "$WIFI_IP" ]; then
  echo ""
  echo "Checking iPhone WiFi IP: $WIFI_IP"
  if command -v route >/dev/null 2>&1; then
    echo "Mac route to iPhone WiFi IP:"
    route -n get "$WIFI_IP" 2>/dev/null | awk '/interface:|gateway:|source address:|ifscope:/ { print "  " $0 }' || true
  fi
  if ping -c 1 "$WIFI_IP" >/dev/null 2>&1; then
    pass "LAN ping to iPhone WiFi IP"
  else
    fail "LAN ping to iPhone WiFi IP" "Mac and iPhone may be on different subnets, guest WiFi, AP/client isolation may be enabled, the Mac may be routing through Ethernet/WiFi on another router, or a VPN/proxy may be stealing local routes."
  fi
  check_http_status "WiFi" "$WIFI_IP"
  check_tcp_port "WiFi RemotePairing" "$WIFI_IP" "49152" "For wireless start/restart, pair in Xcode with USB first, keep iPhone unlocked, and ensure iPhone is connected to WiFi."
else
  warn "No iPhone WiFi IP provided" "Usage: bash scripts/diagnose_usb_wifi.sh <WiFi IP> <Tailscale IP>"
fi

echo ""
if command -v tailscale >/dev/null 2>&1; then
  pass "Tailscale CLI available"
  if tailscale status >/tmp/tailscale_status.txt 2>/tmp/tailscale_status.err; then
    pass "Tailscale status works on Mac"
  else
    fail "Tailscale status failed on Mac" "Open Tailscale on the Mac and log in."
  fi
  if tailscale netcheck >/tmp/tailscale_netcheck.txt 2>/dev/null; then
    echo "Tailscale netcheck summary:"
    sed -n '1,12p' /tmp/tailscale_netcheck.txt | sed 's/^/  /'
  fi
else
  fail "Tailscale CLI available" "Install Tailscale or skip Tailscale checks."
fi

if [ -n "$TAILSCALE_IP" ]; then
  echo ""
  echo "Checking iPhone Tailscale IP: $TAILSCALE_IP"
  if command -v tailscale >/dev/null 2>&1; then
    if tailscale ping -c 3 "$TAILSCALE_IP" >/tmp/tailscale_ping.txt 2>/tmp/tailscale_ping.err; then
      pass "Tailscale ping to iPhone"
      sed -n '1,6p' /tmp/tailscale_ping.txt | sed 's/^/     /'
    else
      fail "Tailscale ping to iPhone" "Check that iPhone Tailscale is connected. On iPhone, disable other VPN/proxy apps during setup and consider VPN On Demand."
    fi
  fi
  check_http_status "Tailscale" "$TAILSCALE_IP"
  check_tcp_port "Tailscale RemotePairing" "$TAILSCALE_IP" "49152" "Remote start/restart needs this port. If it closed after WiFi -> cellular handoff, wait for Tailscale to reconnect and retry; if it stays closed, start WDA on WiFi first and keep controlling it after leaving WiFi."
else
  warn "No iPhone Tailscale IP provided" "Pass the 100.x.y.z IP to check the Tailscale path."
fi

echo ""
echo "=== Result: $OK passed, $WARN warning(s), $FAIL failed ==="
if [ "$FAIL" -eq 0 ]; then
  echo "Ready: network checks look good. If WDA still fails, inspect /tmp/wda_run.log and the phone screen."
else
  echo "Fix the failed layer first. Do not continue to 5G/remote use until WiFi or Tailscale status works."
fi
