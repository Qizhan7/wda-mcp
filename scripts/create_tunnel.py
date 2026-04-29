#!/usr/bin/env python3.13
"""Create a pymobiledevice3 TCP tunnel. Run with sudo.
Usage: sudo python3.13 scripts/create_tunnel.py <DEVICE_ID> <TAILSCALE_IP> <PAIRING_PORT>
Writes "<address> <port>" to /tmp/wda_tunnel.txt when ready.
"""
import asyncio, sys

async def main():
    from pymobiledevice3.remote.tunnel_service import (
        create_core_device_tunnel_service_using_remotepairing,
        start_tunnel, TunnelProtocol,
    )
    device_id = sys.argv[1]
    tailscale_ip = sys.argv[2]
    pairing_port = int(sys.argv[3])
    svc = await create_core_device_tunnel_service_using_remotepairing(
        device_id, tailscale_ip, pairing_port)
    async with start_tunnel(svc, protocol=TunnelProtocol.TCP) as t:
        with open("/tmp/wda_tunnel.txt", "w") as f:
            f.write(f"{t.address} {t.port}")
        await asyncio.sleep(999999)

asyncio.run(main())
