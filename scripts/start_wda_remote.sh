#!/bin/bash
# Start WDA remotely via Tailscale — no USB, no same network needed.
# Usage: ./start_wda_remote.sh <TAILSCALE_IP> <DEVICE_UDID> <BUNDLE_ID>
#
# Example:
#   ./start_wda_remote.sh 100.71.146.51 00008120-000854941A3B401E com.yourname.WebDriverAgentRunner.xctrunner

set -e

TAILSCALE_IP="${1:?Usage: $0 <TAILSCALE_IP> <DEVICE_UDID> <BUNDLE_ID>}"
DEVICE_UDID="${2:?Missing DEVICE_UDID}"
BUNDLE_ID="${3:?Missing BUNDLE_ID}"

echo "=== WDA Remote Start ==="
echo "Tailscale IP: $TAILSCALE_IP"
echo "Device UDID:  $DEVICE_UDID"
echo "Bundle ID:    $BUNDLE_ID"

# Step 0: Apply DTX patch if needed
echo ""
echo "[1/4] Checking pymobiledevice3 patch..."
python3.12 "$(dirname "$0")/patch_pymobiledevice3.py"

# Step 1: Check RemotePairing port
echo ""
echo "[2/4] Checking RemotePairing service..."
python3.12 -c "
import socket; s=socket.socket(); s.settimeout(3)
s.connect(('$TAILSCALE_IP', 49152)); s.close()
print('RemotePairing port OPEN')
" || { echo "ERROR: Port 49152 closed. Is iPhone WiFi toggle ON?"; exit 1; }

# Step 2: Create tunnel (needs sudo)
echo ""
echo "[3/4] Creating tunnel via Tailscale (needs sudo)..."
pkill -f "pymobiledevice3.*xcuitest" 2>/dev/null || true
rm -f /tmp/wda_tunnel.txt

sudo python3.13 -c "
import asyncio
async def main():
    from pymobiledevice3.remote.tunnel_service import (
        create_core_device_tunnel_service_using_remotepairing,
        start_tunnel, TunnelProtocol,
    )
    svc = await create_core_device_tunnel_service_using_remotepairing(
        '$DEVICE_UDID', '$TAILSCALE_IP', 49152)
    async with start_tunnel(svc, protocol=TunnelProtocol.TCP) as t:
        with open('/tmp/wda_tunnel.txt', 'w') as f:
            f.write(f'{t.address} {t.port}')
        print(f'Tunnel: {t.address}:{t.port}')
        await asyncio.sleep(999999)
asyncio.run(main())
" &
TUNNEL_PID=$!

# Wait for tunnel
for i in $(seq 1 30); do
    sleep 1
    if [ -f /tmp/wda_tunnel.txt ]; then
        read ADDR PORT < /tmp/wda_tunnel.txt
        break
    fi
done

if [ -z "$ADDR" ]; then
    echo "ERROR: Tunnel creation timed out"
    kill $TUNNEL_PID 2>/dev/null
    exit 1
fi
echo "Tunnel ready: $ADDR:$PORT"

# Step 3: Start WDA
echo ""
echo "[4/4] Starting WDA..."
python3.12 -m pymobiledevice3 developer dvt xcuitest \
    --rsd "$ADDR" "$PORT" "$BUNDLE_ID" \
    --env USE_PORT=8100 --env MJPEG_SERVER_PORT=9100 &
WDA_PID=$!

# Wait for WDA
echo "Waiting for WDA to start..."
for i in $(seq 1 30); do
    sleep 2
    if curl -m 3 -s "http://$TAILSCALE_IP:8100/status" 2>/dev/null | grep -q '"ready" : true'; then
        echo ""
        echo "========================================="
        echo "  WDA READY!"
        echo "  URL: http://$TAILSCALE_IP:8100"
        echo "  Tunnel PID: $TUNNEL_PID"
        echo "  XCUITest PID: $WDA_PID"
        echo "========================================="
        echo ""
        echo "Keep this terminal open. Ctrl+C to stop."
        wait
        exit 0
    fi
done

echo "ERROR: WDA did not start within 60 seconds. Check /tmp/wda_run.log"
exit 1
