"""WDA-MCP: WebDriverAgent iPhone Control via MCP"""

import os
import re
import json
import time
import base64
import subprocess
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("wda-mcp")

WDA_TAILSCALE_IP = os.environ.get("WDA_TAILSCALE_IP", "")
WDA_DEVICE_ID = os.environ.get("WDA_DEVICE_ID", "")
WDA_BUNDLE_ID = os.environ.get("WDA_BUNDLE_ID", "com.example.WebDriverAgentRunner.xctrunner")
WDA_PROJECT_DIR = os.environ.get("WDA_PROJECT_DIR", os.path.expanduser("~/Desktop/WebDriverAgent"))
SCREENSHOTS_DIR = os.environ.get("WDA_SCREENSHOTS_DIR", os.path.expanduser("~/screenshots"))

_wda_session_id: str | None = None
_wda_base: str | None = None


def _wda_discover_ip() -> str:
    global _wda_base
    if WDA_TAILSCALE_IP:
        try:
            url = f"http://{WDA_TAILSCALE_IP}:8100/status"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                _wda_base = f"http://{WDA_TAILSCALE_IP}:8100"
                return _wda_base
        except Exception:
            pass
    try:
        with open("/tmp/wda_run.log", "r") as f:
            for line in f:
                if "ServerURLHere" in line:
                    m = re.search(r"http://[\d.]+:8100", line)
                    if m:
                        _wda_base = m.group(0)
                        return _wda_base
    except FileNotFoundError:
        pass
    for ip in ["192.168.1.14", "192.168.1.17", "192.168.1.15", "192.168.1.16"]:
        try:
            url = f"http://{ip}:8100/status"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                _wda_base = f"http://{ip}:8100"
                return _wda_base
        except Exception:
            continue
    return ""


def _wda_request(method: str, path: str, body: dict | None = None) -> dict:
    base = _wda_base or _wda_discover_ip()
    if not base:
        return {"error": "WDA not reachable. Is it running? Try wda_start() first."}
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": str(e)}


def _wda_get_session() -> str:
    global _wda_session_id
    if _wda_session_id:
        r = _wda_request("GET", f"/session/{_wda_session_id}/window/size")
        if "error" not in r:
            return _wda_session_id
    r = _wda_request("POST", "/session", {
        "capabilities": {"alwaysMatch": {"platformName": "iOS"}}
    })
    _wda_session_id = r.get("sessionId") or r.get("value", {}).get("sessionId", "")
    return _wda_session_id


@mcp.tool()
def wda_status() -> str:
    """Check if WDA is running and ready. Returns device info and IP."""
    r = _wda_request("GET", "/status")
    if "error" in r:
        return f"WDA not reachable: {r.get('error', 'unknown')}"
    v = r.get("value", {})
    return f"WDA ready={v.get('ready', False)}, iOS {v.get('os', {}).get('version', '?')}, IP {v.get('ios', {}).get('ip', '?')}, base={_wda_base}"


@mcp.tool()
def wda_info() -> str:
    """Get comprehensive device info in one call: device, battery, screen, active app, and visible text."""
    import xml.etree.ElementTree as ET
    lines = []
    sid = _wda_get_session()

    # Device info
    r = _wda_request("GET", "/status")
    if "error" not in r:
        v = r.get("value", {})
        lines.append(f"Device: {v.get('os', {}).get('name', '?')} {v.get('os', {}).get('version', '?')}")
        lines.append(f"IP: {v.get('ios', {}).get('ip', 'unknown')}")

    # Battery
    r = _wda_request("GET", f"/session/{sid}/wda/batteryInfo")
    if "error" not in r:
        batt = r.get("value", {})
        level = int(batt.get("level", 0) * 100)
        state = {0: "unknown", 1: "unplugged", 2: "charging", 3: "full"}.get(batt.get("state", 0), "?")
        lines.append(f"Battery: {level}% ({state})")

    # Screen size
    r = _wda_request("GET", f"/session/{sid}/window/size")
    if "error" not in r:
        sz = r.get("value", {})
        lines.append(f"Screen: {sz.get('width', '?')}x{sz.get('height', '?')} points")

    # Active app
    r = _wda_request("GET", f"/session/{sid}/wda/activeAppInfo")
    if "error" not in r:
        app = r.get("value", {})
        lines.append(f"Active app: {app.get('name', '?')} ({app.get('bundleId', '?')})")
        lines.append(f"PID: {app.get('pid', '?')}")

    # Visible text (from wda_check logic)
    r = _wda_request("GET", f"/session/{sid}/source")
    if "error" not in r:
        try:
            root = ET.fromstring(r.get("value", "<x/>"))
            texts = []
            for elem in root.iter():
                label = elem.attrib.get("label", "").strip()
                if label and label not in texts and len(label) < 100:
                    texts.append(label)
            lines.append(f"\nVisible text ({len(texts)} items):")
            for t in texts[:20]:
                lines.append(f"  - {t}")
            if len(texts) > 20:
                lines.append(f"  ... and {len(texts) - 20} more")
        except Exception:
            pass

    return "\n".join(lines)


@mcp.tool()
def wda_screenshot() -> str:
    """Take a screenshot (heavy, costs thousands of tokens). Use wda_check first for text-based viewing. Only use screenshot when text is insufficient — e.g. checking images, layout, or when wda_check output is unclear."""
    sid = _wda_get_session()
    r = _wda_request("GET", f"/session/{sid}/screenshot")
    if "error" in r:
        return f"Screenshot failed: {r.get('error', 'unknown')}"
    img_data = base64.b64decode(r.get("value", ""))
    path = os.path.join(SCREENSHOTS_DIR, f"wda_{int(time.time())}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(img_data)
    return f"Screenshot saved: {path}"


@mcp.tool()
def wda_tap(x: float, y: float) -> str:
    """Tap a point on iPhone screen. iPhone 14 Pro: 393x852 points."""
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/actions", {
        "actions": [{
            "type": "pointer",
            "id": "finger1",
            "parameters": {"pointerType": "touch"},
            "actions": [
                {"type": "pointerMove", "duration": 0, "x": int(x), "y": int(y)},
                {"type": "pointerDown", "button": 0},
                {"type": "pause", "duration": 100},
                {"type": "pointerUp", "button": 0}
            ]
        }]
    })
    if "error" in r:
        return f"Tap failed: {r.get('error', 'unknown')}"
    return f"Tapped ({x}, {y})"


@mcp.tool()
def wda_swipe(fromX: float, fromY: float, toX: float, toY: float, duration: float = 0.1) -> str:
    """Swipe on iPhone. Coords are points (393x852). duration in seconds.
    Home gesture: (196,845)->(196,100) duration=0.08"""
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration", {
        "fromX": fromX, "fromY": fromY, "toX": toX, "toY": toY, "duration": duration
    })
    if "error" in r:
        return f"Swipe failed: {r.get('error', 'unknown')}"
    return f"Swiped ({fromX},{fromY}) -> ({toX},{toY})"


@mcp.tool()
def wda_type(text: str) -> str:
    """Type text on iPhone. Tap an input field first to focus it."""
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/wda/keys", {"value": list(text)})
    if "error" in r:
        return f"Type failed: {r.get('error', 'unknown')}"
    return f"Typed: {text}"


@mcp.tool()
def wda_home() -> str:
    """Go to home screen. WARNING: if already on home screen, this may open the app switcher instead. Use wda_check first to confirm current screen before navigating."""
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/wda/homescreen")
    if "error" in r:
        r = _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration", {
            "fromX": 196, "fromY": 845, "toX": 196, "toY": 100, "duration": 0.08
        })
        if "error" in r:
            return f"Home failed: {r.get('error', 'unknown')}"
        return "Home (swipe fallback)"
    return "Home"


@mcp.tool()
def wda_back() -> str:
    """Go back to previous page. Uses left edge swipe (iOS back gesture). Also tries tap '返回' button as fallback."""
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration", {
        "fromX": 0, "fromY": 400, "toX": 250, "toY": 400, "duration": 0.2
    })
    if "error" in r:
        return f"Back failed: {r.get('error', 'unknown')}"
    return "Back (edge swipe)"


@mcp.tool()
def wda_scroll(direction: str = "down") -> str:
    """Scroll the screen. direction: 'down', 'up', 'left', 'right'."""
    sid = _wda_get_session()
    swipes = {
        "down":  {"fromX": 196, "fromY": 600, "toX": 196, "toY": 250, "duration": 0.3},
        "up":    {"fromX": 196, "fromY": 250, "toX": 196, "toY": 600, "duration": 0.3},
        "left":  {"fromX": 350, "fromY": 426, "toX": 50, "toY": 426, "duration": 0.3},
        "right": {"fromX": 50, "fromY": 426, "toX": 350, "toY": 426, "duration": 0.3},
    }
    params = swipes.get(direction.lower())
    if not params:
        return f"Unknown direction '{direction}'. Use: down, up, left, right"
    r = _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration", params)
    if "error" in r:
        return f"Scroll failed: {r.get('error', 'unknown')}"
    return f"Scrolled {direction}"


@mcp.tool()
def wda_long_press(x: float, y: float, duration: float = 1.0) -> str:
    """Long press at a point. duration in seconds (default 1s). Useful for context menus, voice messages, etc."""
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/actions", {
        "actions": [{
            "type": "pointer", "id": "finger1",
            "parameters": {"pointerType": "touch"},
            "actions": [
                {"type": "pointerMove", "duration": 0, "x": int(x), "y": int(y)},
                {"type": "pointerDown", "button": 0},
                {"type": "pause", "duration": int(duration * 1000)},
                {"type": "pointerUp", "button": 0}
            ]
        }]
    })
    if "error" in r:
        return f"Long press failed: {r.get('error', 'unknown')}"
    return f"Long pressed ({x}, {y}) for {duration}s"


@mcp.tool()
def wda_notifications() -> str:
    """Pull down notification center and read all visible notifications. Text-based, no screenshot."""
    import xml.etree.ElementTree as ET
    sid = _wda_get_session()
    # Pull down from top
    _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration", {
        "fromX": 196, "fromY": 5, "toX": 196, "toY": 500, "duration": 0.3
    })
    time.sleep(0.5)
    r = _wda_request("GET", f"/session/{sid}/source")
    if "error" in r:
        return f"Failed: {r.get('error')}"
    try:
        root = ET.fromstring(r.get("value", "<x/>"))
        texts = []
        for elem in root.iter():
            label = elem.attrib.get("label", "").strip()
            if label and label not in texts and len(label) < 200:
                texts.append(label)
        result = f"Notifications ({len(texts)} items):\n"
        result += "\n".join(f"  - {t}" for t in texts[:30])
        # Dismiss notification center
        _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration", {
            "fromX": 196, "fromY": 500, "toX": 196, "toY": 5, "duration": 0.3
        })
        return result
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def wda_clipboard() -> str:
    """Read the iPhone clipboard content. Returns the text currently copied."""
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/wda/getPasteboard")
    if "error" in r:
        return f"Clipboard failed: {r.get('error', 'unknown')}"
    content = r.get("value", "")
    if content:
        import base64 as b64
        try:
            return f"Clipboard: {b64.b64decode(content).decode('utf-8')}"
        except Exception:
            return f"Clipboard (raw): {content}"
    return "Clipboard is empty"


def _is_home_screen() -> bool:
    """Check if we're on the home screen (app name is empty)."""
    sid = _wda_get_session()
    r = _wda_request("GET", f"/session/{sid}/source")
    if "error" in r:
        return False
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(r.get("value", "<x/>"))
        name = root.attrib.get("name", "").strip()
        return name == "" or name == "SpringBoard"
    except Exception:
        return False


@mcp.tool()
def wda_launch(name: str) -> str:
    """Open any app by name using Spotlight search. Works for any installed app, no cache needed."""
    sid = _wda_get_session()
    # Go home first
    _wda_request("POST", f"/session/{sid}/wda/homescreen")
    time.sleep(0.5)
    if not _is_home_screen():
        _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration",
                     {"fromX": 196, "fromY": 845, "toX": 196, "toY": 100, "duration": 0.08})
        time.sleep(0.5)

    # Pull down for Spotlight search
    _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration",
                 {"fromX": 196, "fromY": 400, "toX": 196, "toY": 600, "duration": 0.3})
    time.sleep(0.5)

    # Type app name and tap first result (top match position is consistent)
    _wda_request("POST", f"/session/{sid}/wda/keys", {"value": list(name)})
    time.sleep(0.5)

    # Tap the top search result icon — Spotlight puts the best match icon at (64, 154)
    _wda_request("POST", f"/session/{sid}/actions", {
        "actions": [{"type": "pointer", "id": "f1",
                     "parameters": {"pointerType": "touch"},
                     "actions": [
                         {"type": "pointerMove", "duration": 0, "x": 64, "y": 154},
                         {"type": "pointerDown", "button": 0},
                         {"type": "pause", "duration": 100},
                         {"type": "pointerUp", "button": 0}]}]
    })
    time.sleep(0.5)
    return f"Launched '{name}' via Spotlight"




@mcp.tool()
def wda_source() -> str:
    """Get UI element tree of current screen. Returns XML with labels and coordinates."""
    sid = _wda_get_session()
    r = _wda_request("GET", f"/session/{sid}/source")
    if "error" in r:
        return f"Source failed: {r.get('error', 'unknown')}"
    src = str(r.get("value", ""))
    if len(src) > 8000:
        src = src[:8000] + "\n... (truncated)"
    return src


@mcp.tool()
def wda_find(text: str) -> str:
    """Find UI elements matching text. Returns label, type, and tap coordinates. No screenshot needed."""
    sid = _wda_get_session()
    r = _wda_request("GET", f"/session/{sid}/source")
    if "error" in r:
        return f"Find failed: {r.get('error', 'unknown')}"
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(r.get("value", "<x/>"))
        matches = []
        text_lower = text.lower()
        for elem in root.iter():
            label = elem.attrib.get("label", "")
            name = elem.attrib.get("name", "")
            value = elem.attrib.get("value", "")
            if text_lower in label.lower() or text_lower in name.lower() or text_lower in value.lower():
                x = int(elem.attrib.get("x", 0))
                y = int(elem.attrib.get("y", 0))
                w = int(elem.attrib.get("width", 0))
                h = int(elem.attrib.get("height", 0))
                cx, cy = x + w // 2, y + h // 2
                matches.append(f"  '{label or name}' ({elem.attrib.get('type', '?')}) → tap({cx}, {cy})")
        if not matches:
            return f"No elements matching '{text}'"
        return f"Found {len(matches)} match(es):\n" + "\n".join(matches[:10])
    except Exception as e:
        return f"Parse error: {e}"


@mcp.tool()
def wda_tap_text(text: str) -> str:
    """Find an element by text and tap it. Auto-retries for 3 seconds if not found (handles page loading)."""
    import xml.etree.ElementTree as ET
    sid = _wda_get_session()

    for attempt in range(3):
        r = _wda_request("GET", f"/session/{sid}/source")
        if "error" in r:
            return f"Find failed: {r.get('error', 'unknown')}"
        try:
            root = ET.fromstring(r.get("value", "<x/>"))
        text_lower = text.lower()
        for elem in root.iter():
            label = elem.attrib.get("label", "")
            name = elem.attrib.get("name", "")
            value = elem.attrib.get("value", "")
            if text_lower in label.lower() or text_lower in name.lower() or text_lower in value.lower():
                x = int(elem.attrib.get("x", 0))
                y = int(elem.attrib.get("y", 0))
                w = int(elem.attrib.get("width", 0))
                h = int(elem.attrib.get("height", 0))
                cx, cy = x + w // 2, y + h // 2
                tap_r = _wda_request("POST", f"/session/{sid}/actions", {
                    "actions": [{
                        "type": "pointer", "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": cx, "y": cy},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 100},
                            {"type": "pointerUp", "button": 0}
                        ]
                    }]
                })
                if "error" in tap_r:
                    return f"Found '{label or name}' but tap failed: {tap_r['error']}"
                return f"Tapped '{label or name}' at ({cx}, {cy})"
            # Not found — wait and retry
            if attempt < 2:
                time.sleep(0.5)
                continue
            return f"No element matching '{text}' found on screen (tried 3 times)"
        except Exception as e:
            return f"Error: {e}"
    return f"No element matching '{text}' found"


@mcp.tool()
def wda_check() -> str:
    """Primary way to see the screen — returns current app and all visible text. Use this FIRST before wda_screenshot. Only fall back to screenshot if text is insufficient."""
    sid = _wda_get_session()
    r = _wda_request("GET", f"/session/{sid}/source")
    if "error" in r:
        return f"Check failed: {r.get('error', 'unknown')}"
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(r.get("value", "<x/>"))
        app_name = root.attrib.get("name", root.attrib.get("label", "unknown"))
        app_type = root.attrib.get("type", "")
        texts = []
        for elem in root.iter():
            label = elem.attrib.get("label", "").strip()
            value = elem.attrib.get("value", "").strip()
            if label and label not in texts and len(label) < 100:
                texts.append(label)
            if value and value != label and value not in texts and len(value) < 100:
                texts.append(value)
        summary = f"App: {app_name}\n"
        summary += f"Visible text ({len(texts)} items):\n"
        summary += "\n".join(f"  - {t}" for t in texts[:30])
        if len(texts) > 30:
            summary += f"\n  ... and {len(texts) - 30} more"
        return summary
    except Exception as e:
        return f"Parse error: {e}"


def _patch_pymobiledevice3_dtx():
    """Patch pymobiledevice3 to register XCTest services early (fixes xcuitest over RSD tunnels).
    See: https://github.com/doronz88/pymobiledevice3/pull/1665"""
    import site, pathlib
    for base in site.getsitepackages() + [site.getusersitepackages()]:
        target = pathlib.Path(base) / "pymobiledevice3/services/dvt/testmanaged/xcuitest.py"
        if not target.exists():
            continue
        code = target.read_text()
        if "REGISTER_SERVICES" in code:
            return
        old = '    OLD_SERVICE_NAME = "com.apple.testmanagerd.lockdown"'
        new = (
            '    OLD_SERVICE_NAME = "com.apple.testmanagerd.lockdown"\n'
            '    REGISTER_SERVICES = (\n'
            '        XCTestManager_IDEInterface,\n'
            '        XCTestManager_DaemonConnectionInterface,\n'
            '        XCTestDriverInterface,\n'
            '    )'
        )
        target.write_text(code.replace(old, new))
        return


@mcp.tool()
def wda_start() -> str:
    """Start/restart WDA service on iPhone. Tries remote (Tailscale) first, falls back to local xcodebuild."""
    global _wda_base, _wda_session_id
    _wda_base = None
    _wda_session_id = None
    subprocess.run(["pkill", "-f", "xcodebuild.*test"], capture_output=True)
    subprocess.run(["pkill", "-f", "pymobiledevice3.*xcuitest"], capture_output=True)

    if WDA_TAILSCALE_IP:
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((WDA_TAILSCALE_IP, 49152))
            s.close()

            _patch_pymobiledevice3_dtx()

            tunnel_script = f"""
import asyncio
async def main():
    from pymobiledevice3.remote.tunnel_service import (
        create_core_device_tunnel_service_using_remotepairing,
        start_tunnel, TunnelProtocol,
    )
    svc = await create_core_device_tunnel_service_using_remotepairing(
        "{WDA_DEVICE_ID}", "{WDA_TAILSCALE_IP}", 49152)
    async with start_tunnel(svc, protocol=TunnelProtocol.TCP) as t:
        with open("/tmp/wda_tunnel.txt", "w") as f:
            f.write(f"{{t.address}} {{t.port}}")
        await asyncio.sleep(999999)
asyncio.run(main())
"""
            subprocess.Popen(
                ["sudo", "-S", "python3.13", "-c", tunnel_script],
                stdin=subprocess.DEVNULL,
                stdout=open("/tmp/wda_tunnel.log", "w"), stderr=subprocess.STDOUT
            )
            for _ in range(30):
                time.sleep(0.5)
                try:
                    with open("/tmp/wda_tunnel.txt") as f:
                        addr, port = f.read().strip().split()
                    break
                except Exception:
                    continue
            else:
                return "Tunnel creation timed out. Ensure sudo is passwordless or try again."

            xcuitest_cmd = (
                f"python3.12 -m pymobiledevice3 developer dvt xcuitest "
                f"--rsd {addr} {port} {WDA_BUNDLE_ID} "
                f"--env USE_PORT=8100 --env MJPEG_SERVER_PORT=9100"
            )
            subprocess.Popen(xcuitest_cmd, shell=True,
                             stdout=open("/tmp/wda_run.log", "w"), stderr=subprocess.STDOUT)
            return f"WDA starting via Tailscale tunnel ({addr}:{port}). Check wda_status() in ~15 seconds."
        except (socket.error, OSError):
            pass

    cmd = f"cd {WDA_PROJECT_DIR} && nohup xcodebuild test-without-building -project WebDriverAgent.xcodeproj -scheme WebDriverAgentRunner -destination 'id={WDA_DEVICE_ID}' > /tmp/wda_run.log 2>&1 &"
    subprocess.Popen(cmd, shell=True)
    return "WDA starting via xcodebuild (local). Check wda_status() in ~15 seconds."


@mcp.tool()
def wda_renew() -> str:
    """Rebuild WDA to renew 7-day signing certificate. Takes 2-3 min."""
    cmd = f"cd {WDA_PROJECT_DIR} && xcodebuild build-for-testing -project WebDriverAgent.xcodeproj -scheme WebDriverAgentRunner -destination 'id={WDA_DEVICE_ID}' -allowProvisioningUpdates"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    if "BUILD SUCCEEDED" in result.stdout:
        return "WDA renewal SUCCEEDED. Run wda_start() to restart."
    else:
        err = result.stderr[-500:] if result.stderr else result.stdout[-500:]
        return f"WDA renewal FAILED: {err}"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()
    if args.http:
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = 8200
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
