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
def wda_screenshot() -> str:
    """Take a screenshot of the iPhone screen. Returns the saved file path."""
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
    r = _wda_request("POST", f"/session/{sid}/wda/tap/0", {"x": x, "y": y})
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
    """Go to home screen (swipe up from bottom, for Face ID iPhones)."""
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration", {
        "fromX": 196, "fromY": 845, "toX": 196, "toY": 100, "duration": 0.08
    })
    if "error" in r:
        return f"Home failed: {r.get('error', 'unknown')}"
    return "Swiped to home screen"


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
def wda_start() -> str:
    """Start/restart WDA service on iPhone."""
    global _wda_base, _wda_session_id
    _wda_base = None
    _wda_session_id = None
    subprocess.run(["pkill", "-f", "xcodebuild.*test-without-building"], capture_output=True)
    cmd = f"cd {WDA_PROJECT_DIR} && nohup xcodebuild test-without-building -project WebDriverAgent.xcodeproj -scheme WebDriverAgentRunner -destination 'id={WDA_DEVICE_ID}' > /tmp/wda_run.log 2>&1 &"
    subprocess.Popen(cmd, shell=True)
    return "WDA starting in background. Check wda_status() in ~15 seconds."


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
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8200)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
