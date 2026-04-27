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

def _load_env_file(path: str) -> None:
    """Load simple KEY=VALUE pairs without overriding the parent environment."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env_file(os.path.join(os.path.dirname(__file__), ".env"))

WDA_TAILSCALE_IP = os.environ.get("WDA_TAILSCALE_IP", "")
WDA_DEVICE_ID = os.environ.get("WDA_DEVICE_ID", "")
WDA_BUNDLE_ID = os.environ.get("WDA_BUNDLE_ID", "com.example.WebDriverAgentRunner.xctrunner")
WDA_PROJECT_DIR = os.path.expanduser(os.environ.get("WDA_PROJECT_DIR", "~/Desktop/WebDriverAgent"))
SCREENSHOTS_DIR = os.path.expanduser(os.environ.get("WDA_SCREENSHOTS_DIR", "~/screenshots"))

_wda_session_id: str | None = None
_wda_base: str | None = None
_screen: dict | None = None  # {"w": 393, "h": 852, "cx": 196, "cy": 426, ...}

SCREEN_CACHE = os.path.join(os.path.dirname(__file__), ".screen_cache.json")

def _get_screen() -> dict:
    """Get screen dimensions and key coordinates. Cached after first call."""
    global _screen
    if _screen:
        return _screen
    if os.path.exists(SCREEN_CACHE):
        with open(SCREEN_CACHE) as f:
            _screen = json.load(f)
            return _screen
    sid = _wda_get_session()
    r = _wda_request("GET", f"/session/{sid}/window/size")
    if "error" in r:
        # Fallback to iPhone 14 Pro defaults
        w, h = 393, 852
    else:
        w = r.get("value", {}).get("width", 393)
        h = r.get("value", {}).get("height", 852)
    _screen = {
        "w": w, "h": h,
        "cx": w // 2,
        "cy": h // 2,
        "bottom": h - 7,
        "top": 5,
        "spotlight_icon_x": None,
        "spotlight_icon_y": None,
    }
    # Calibrate Spotlight position by actually doing a search
    import xml.etree.ElementTree as ET
    try:
        _wda_request("POST", f"/session/{sid}/wda/homescreen")
        time.sleep(0.5)
        _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration",
                     {"fromX": w // 2, "fromY": h // 2, "toX": w // 2, "toY": int(h * 0.7), "duration": 0.3})
        time.sleep(0.5)
        _wda_request("POST", f"/session/{sid}/wda/keys", {"value": list("设置")})
        time.sleep(1)
        r2 = _wda_request("GET", f"/session/{sid}/source")
        if "error" not in r2:
            root = ET.fromstring(r2.get("value", "<x/>"))
            for elem in root.iter():
                label = elem.attrib.get("label", "")
                etype = elem.attrib.get("type", "")
                if "设置" in label and "Icon" in etype:
                    ix = int(elem.attrib.get("x", 0))
                    iy = int(elem.attrib.get("y", 0))
                    iw = int(elem.attrib.get("width", 0))
                    ih = int(elem.attrib.get("height", 0))
                    _screen["spotlight_icon_x"] = ix + iw // 2
                    _screen["spotlight_icon_y"] = iy + ih // 2
                    break
        # Dismiss Spotlight
        _wda_request("POST", f"/session/{sid}/wda/homescreen")
    except Exception:
        pass
    # Fallback if calibration failed
    if not _screen["spotlight_icon_x"]:
        _screen["spotlight_icon_x"] = int(w * 0.16)
        _screen["spotlight_icon_y"] = int(h * 0.18)
    with open(SCREEN_CACHE, "w") as f:
        json.dump(_screen, f)
    return _screen


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
    """Tap a point on iPhone screen. Use wda_info to check screen size (e.g. 393x852 points)."""
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
    """Swipe on iPhone. Coords are points. Use wda_info to check screen size.
    Home gesture: use wda_home instead."""
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
            "fromX": _get_screen()["cx"], "fromY": _get_screen()["bottom"], "toX": _get_screen()["cx"], "toY": 100, "duration": 0.08
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
        "fromX": 0, "fromY": _get_screen()["cy"], "toX": int(_get_screen()["w"] * 0.64), "toY": _get_screen()["cy"], "duration": 0.2
    })
    if "error" in r:
        return f"Back failed: {r.get('error', 'unknown')}"
    return "Back (edge swipe)"


@mcp.tool()
def wda_scroll(direction: str = "down") -> str:
    """Scroll the screen. direction: 'down', 'up', 'left', 'right'."""
    sid = _wda_get_session()
    swipes = {
        "down":  {"fromX": _get_screen()["cx"], "fromY": int(_get_screen()["h"] * 0.7), "toX": _get_screen()["cx"], "toY": int(_get_screen()["h"] * 0.3), "duration": 0.3},
        "up":    {"fromX": _get_screen()["cx"], "fromY": int(_get_screen()["h"] * 0.3), "toX": _get_screen()["cx"], "toY": int(_get_screen()["h"] * 0.7), "duration": 0.3},
        "left":  {"fromX": int(_get_screen()["w"] * 0.9), "fromY": _get_screen()["cy"], "toX": int(_get_screen()["w"] * 0.1), "toY": _get_screen()["cy"], "duration": 0.3},
        "right": {"fromX": int(_get_screen()["w"] * 0.1), "fromY": _get_screen()["cy"], "toX": int(_get_screen()["w"] * 0.9), "toY": _get_screen()["cy"], "duration": 0.3},
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
        "fromX": _get_screen()["cx"], "fromY": _get_screen()["top"], "toX": _get_screen()["cx"], "toY": _get_screen()["cy"], "duration": 0.3
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
            "fromX": _get_screen()["cx"], "fromY": _get_screen()["cy"], "toX": _get_screen()["cx"], "toY": _get_screen()["top"], "duration": 0.3
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
                     {"fromX": _get_screen()["cx"], "fromY": _get_screen()["bottom"], "toX": _get_screen()["cx"], "toY": 100, "duration": 0.08})
        time.sleep(0.5)

    # Pull down for Spotlight search
    _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration",
                 {"fromX": _get_screen()["cx"], "fromY": _get_screen()["cy"], "toX": _get_screen()["cx"], "toY": int(_get_screen()["h"] * 0.7), "duration": 0.3})
    time.sleep(0.5)

    # Type app name and tap first result (top match position is consistent)
    _wda_request("POST", f"/session/{sid}/wda/keys", {"value": list(name)})
    time.sleep(0.5)

    # Tap the top search result icon — Spotlight puts the best match icon at (64, 154)
    _wda_request("POST", f"/session/{sid}/actions", {
        "actions": [{"type": "pointer", "id": "f1",
                     "parameters": {"pointerType": "touch"},
                     "actions": [
                         {"type": "pointerMove", "duration": 0, "x": _get_screen()["spotlight_icon_x"], "y": _get_screen()["spotlight_icon_y"]},
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
    text_lower = text.lower()

    for attempt in range(3):
        r = _wda_request("GET", f"/session/{sid}/source")
        if "error" in r:
            return f"Find failed: {r.get('error', 'unknown')}"
        try:
            root = ET.fromstring(r.get("value", "<x/>"))
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
        except Exception as e:
            return f"Error: {e}"

        if attempt < 2:
            time.sleep(0.5)

    return f"No element matching '{text}' found on screen (tried 3 times)"


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


def _run_http() -> None:
    """Run wda-mcp over streamable HTTP with OAuth + Bearer auth.

    HTTP mode is dangerous to leave unauthenticated — anyone who reaches /mcp can
    control the iPhone (tap, type, screenshot, read clipboard). This runner refuses
    to start without an access token, exposes OAuth metadata so MCP clients can
    enroll, and falls back to a Bearer header check otherwise.
    """
    import json as _json
    import pathlib
    import secrets as _secrets
    import sys as _sys
    import time as _time

    import uvicorn
    import mcp.server.transport_security as _ts
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, RedirectResponse
    from starlette.routing import Route

    cred_file = pathlib.Path.home() / ".wda-oauth.json"
    if cred_file.exists():
        creds = _json.loads(cred_file.read_text())
        client_id = creds.get("client_id", "")
        client_secret = creds.get("client_secret", "")
        access_token = creds.get("access_token", "")
    else:
        client_id = os.environ.get("WDA_OAUTH_CLIENT_ID", "")
        client_secret = os.environ.get("WDA_OAUTH_CLIENT_SECRET", "")
        access_token = os.environ.get("WDA_OAUTH_ACCESS_TOKEN", "")

    if not access_token:
        print(
            "ERROR: wda-mcp HTTP mode refuses to start without an access token.\n"
            "       Generate one: python scripts/generate_oauth_creds.py\n"
            "       Or set WDA_OAUTH_ACCESS_TOKEN (and optional CLIENT_ID/SECRET).",
            file=_sys.stderr,
        )
        _sys.exit(1)

    # FastMCP's default DNS-rebinding protection blocks tunnel-routed Host headers
    # (cloudflared / ngrok). We replace that protection with explicit Bearer auth
    # in the middleware below.
    _orig_init = _ts.TransportSecurityMiddleware.__init__

    def _patched_init(self, settings=None):
        _orig_init(self, _ts.TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
            allowed_hosts=["*"],
        ))

    _ts.TransportSecurityMiddleware.__init__ = _patched_init

    pending_codes: dict = {}

    class OAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            path = request.url.path
            if path in (
                "/oauth/token",
                "/oauth/authorize",
                "/.well-known/oauth-authorization-server",
                "/.well-known/oauth-protected-resource",
            ):
                return await call_next(request)
            client = request.client
            if client and client.host in ("127.0.0.1", "::1", "localhost"):
                return await call_next(request)
            auth = request.headers.get("authorization", "")
            if auth == f"Bearer {access_token}":
                return await call_next(request)
            return JSONResponse({"error": "unauthorized"}, status_code=401)

    app = mcp.streamable_http_app()
    mcp_route = app.routes[0]
    app.routes.append(Route("/", mcp_route.endpoint, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]))

    async def oauth_protected_resource(request: Request):
        base = str(request.base_url).rstrip("/")
        return JSONResponse({"resource": base, "authorization_servers": [base]})

    async def oauth_metadata(request: Request):
        base = str(request.base_url).rstrip("/")
        return JSONResponse({
            "issuer": base,
            "authorization_endpoint": f"{base}/oauth/authorize",
            "token_endpoint": f"{base}/oauth/token",
            "grant_types_supported": ["authorization_code", "client_credentials"],
            "response_types_supported": ["code"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post"],
        })

    async def oauth_authorize(request: Request):
        from urllib.parse import urlencode
        redirect_uri = request.query_params.get("redirect_uri", "")
        state = request.query_params.get("state", "")
        if not redirect_uri:
            return JSONResponse({"error": "missing redirect_uri"}, status_code=400)
        code = _secrets.token_urlsafe(32)
        pending_codes[code] = {"redirect_uri": redirect_uri, "expires_at": _time.time() + 300}
        return RedirectResponse(f"{redirect_uri}?{urlencode({'code': code, 'state': state})}")

    async def oauth_token(request: Request):
        from urllib.parse import unquote_plus
        body = await request.body()
        try:
            params = {
                k: unquote_plus(v)
                for k, v in (x.split("=", 1) for x in body.decode().split("&") if "=" in x)
            }
        except Exception:
            try:
                params = _json.loads(body)
            except Exception:
                return JSONResponse({"error": "invalid_request"}, status_code=400)

        grant_type = params.get("grant_type", "")

        if grant_type == "client_credentials":
            if (client_id and client_secret
                    and params.get("client_id") == client_id
                    and params.get("client_secret") == client_secret):
                return JSONResponse({"access_token": access_token, "token_type": "bearer", "expires_in": 86400})
            return JSONResponse({"error": "invalid_client"}, status_code=401)

        if grant_type == "authorization_code":
            code = params.get("code", "")
            now = _time.time()
            for k in [k for k, v in pending_codes.items() if v["expires_at"] < now]:
                del pending_codes[k]
            pending = pending_codes.pop(code, None)
            if not pending:
                return JSONResponse({"error": "invalid_grant", "error_description": "unknown or expired code"}, status_code=400)
            if params.get("redirect_uri", "") != pending["redirect_uri"]:
                return JSONResponse({"error": "invalid_grant", "error_description": "redirect_uri mismatch"}, status_code=400)
            if client_id and client_secret:
                if (params.get("client_id") != client_id or params.get("client_secret") != client_secret):
                    return JSONResponse({"error": "invalid_client"}, status_code=401)
            return JSONResponse({"access_token": access_token, "token_type": "bearer", "expires_in": 86400})

        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    app.routes.insert(0, Route("/.well-known/oauth-protected-resource", oauth_protected_resource, methods=["GET"]))
    app.routes.insert(1, Route("/.well-known/oauth-authorization-server", oauth_metadata, methods=["GET"]))
    app.routes.insert(2, Route("/oauth/authorize", oauth_authorize, methods=["GET"]))
    app.routes.insert(3, Route("/oauth/token", oauth_token, methods=["POST"]))
    app.add_middleware(OAuthMiddleware)

    host = os.environ.get("WDA_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("WDA_HTTP_PORT", "8200"))
    print(f"wda-mcp HTTP (OAuth + Bearer) on http://{host}:{port}/mcp", flush=True)
    uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info")).run()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()
    if args.http:
        _run_http()
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
