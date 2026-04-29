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
from mcp.types import ToolAnnotations

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
APP_LAYOUTS_DIR = os.path.join(os.path.dirname(__file__), "app_layouts")

# Tool group loading — set WDA_TOOLS env var to load only specific groups.
# Example: WDA_TOOLS=core,wechat  (default: all groups)
_TOOL_GROUPS = {
    "core":   {"wda_check", "wda_screenshot", "wda_tap", "wda_tap_text", "wda_type",
               "wda_swipe", "wda_scroll", "wda_home", "wda_back", "wda_launch",
               "wda_source", "wda_find"},
    "wechat": {"wda_wechat_read", "wda_send_wechat"},
    "learn":  {"wda_learn_app"},
    "util":   {"wda_long_press", "wda_notifications", "wda_clipboard"},
    "setup":  {"wda_status", "wda_start", "wda_renew"},
}
_enabled_groups = os.environ.get("WDA_TOOLS", "").split(",") if os.environ.get("WDA_TOOLS") else list(_TOOL_GROUPS.keys())
_ENABLED = set()
for _g in _enabled_groups:
    _ENABLED |= _TOOL_GROUPS.get(_g.strip(), set())

_RO = ToolAnnotations(readOnlyHint=True)
_RW = ToolAnnotations(readOnlyHint=False)
_DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)

def _tool(func=None, *, annotations=None):
    """Register as MCP tool only if its group is enabled."""
    def decorator(f):
        if f.__name__ in _ENABLED:
            return mcp.tool(annotations=annotations)(f)
        return f
    if func is not None:
        return decorator(func)
    return decorator

_wda_session_id: str | None = None
_wda_base: str | None = None
_screen: dict | None = None  # {"w": 393, "h": 852, "cx": 196, "cy": 426, ...}
_current_chat: str | None = None

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
        with urllib.request.urlopen(req, timeout=30) as resp:
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


@_tool(annotations=_RO)
def wda_status() -> str:
    """Check if WDA is running. Returns device info and IP."""
    r = _wda_request("GET", "/status")
    if "error" in r:
        return f"WDA not reachable: {r.get('error', 'unknown')}"
    v = r.get("value", {})
    return f"WDA ready={v.get('ready', False)}, iOS {v.get('os', {}).get('version', '?')}, IP {v.get('ios', {}).get('ip', '?')}, base={_wda_base}"




@_tool(annotations=_RO)
def wda_screenshot() -> str:
    """Capture screen as PNG. Use wda_check first to save tokens."""
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


@_tool(annotations=_RW)
def wda_tap(x: float, y: float) -> str:
    """Tap a point on screen (x, y in points)."""
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


@_tool(annotations=_RW)
def wda_swipe(fromX: float, fromY: float, toX: float, toY: float, duration: float = 0.1) -> str:
    """Swipe between two points."""
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration", {
        "fromX": fromX, "fromY": fromY, "toX": toX, "toY": toY, "duration": duration
    })
    if "error" in r:
        return f"Swipe failed: {r.get('error', 'unknown')}"
    return f"Swiped ({fromX},{fromY}) -> ({toX},{toY})"


@_tool(annotations=_RW)
def wda_type(text: str) -> str:
    """Type text into the focused input field."""
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/wda/keys", {"value": list(text)})
    if "error" in r:
        return f"Type failed: {r.get('error', 'unknown')}"
    return f"Typed: {text}"


@_tool(annotations=_RW)
def wda_home() -> str:
    """Go to home screen."""
    global _current_chat
    _current_chat = None
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


@_tool(annotations=_RW)
def wda_back() -> str:
    """Go back (iOS left-edge swipe gesture)."""
    global _current_chat
    _current_chat = None
    sid = _wda_get_session()
    r = _wda_request("POST", f"/session/{sid}/wda/dragfromtoforduration", {
        "fromX": 0, "fromY": _get_screen()["cy"], "toX": int(_get_screen()["w"] * 0.64), "toY": _get_screen()["cy"], "duration": 0.2
    })
    if "error" in r:
        return f"Back failed: {r.get('error', 'unknown')}"
    return "Back (edge swipe)"


@_tool(annotations=_RW)
def wda_scroll(direction: str = "down") -> str:
    """Scroll the screen. direction: down/up/left/right."""
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


@_tool(annotations=_RW)
def wda_long_press(x: float, y: float, duration: float = 1.0) -> str:
    """Long press at a point (default 1s)."""
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


@_tool(annotations=_RO)
def wda_notifications() -> str:
    """Read all notifications (pulls down notification center)."""
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


@_tool(annotations=_RO)
def wda_clipboard() -> str:
    """Read clipboard content."""
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


@_tool(annotations=_RW)
def wda_launch(name: str) -> str:
    """Open an app by name via Spotlight search."""
    global _current_chat
    _current_chat = None
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




@_tool(annotations=_RO)
def wda_source() -> str:
    """Get full UI element tree as XML."""
    sid = _wda_get_session()
    r = _wda_request("GET", f"/session/{sid}/source")
    if "error" in r:
        return f"Source failed: {r.get('error', 'unknown')}"
    src = str(r.get("value", ""))
    if len(src) > 8000:
        src = src[:8000] + "\n... (truncated)"
    return src


@_tool(annotations=_RO)
def wda_find(text: str) -> str:
    """Find elements by text. Returns labels and tap coordinates."""
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


@_tool(annotations=_RW)
def wda_tap_text(text: str) -> str:
    """Find element by text and tap it (auto-retries 3x)."""
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


def _tap_text_internal(sid: str, text: str, retries: int = 3) -> tuple[bool, str]:
    """Internal tap_text without MCP overhead. Returns (success, message)."""
    import xml.etree.ElementTree as ET
    text_lower = text.lower()
    for attempt in range(retries):
        r = _wda_request("GET", f"/session/{sid}/source")
        if "error" in r:
            return False, f"Source failed: {r.get('error')}"
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
                    _wda_request("POST", f"/session/{sid}/actions", {
                        "actions": [{"type": "pointer", "id": "finger1",
                                     "parameters": {"pointerType": "touch"},
                                     "actions": [
                                         {"type": "pointerMove", "duration": 0, "x": cx, "y": cy},
                                         {"type": "pointerDown", "button": 0},
                                         {"type": "pause", "duration": 100},
                                         {"type": "pointerUp", "button": 0}]}]
                    })
                    return True, f"Tapped '{label or name}' at ({cx}, {cy})"
        except Exception as e:
            return False, f"Parse error: {e}"
        if attempt < retries - 1:
            time.sleep(0.5)
    return False, f"'{text}' not found"


def _load_app_layout(bundle_id: str) -> dict | None:
    path = os.path.join(APP_LAYOUTS_DIR, f"{bundle_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _tap_cached(sid: str, x: int, y: int):
    _wda_request("POST", f"/session/{sid}/actions", {
        "actions": [{"type": "pointer", "id": "f1",
                     "parameters": {"pointerType": "touch"},
                     "actions": [
                         {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                         {"type": "pointerDown", "button": 0},
                         {"type": "pause", "duration": 100},
                         {"type": "pointerUp", "button": 0}]}]
    })


def _ensure_wechat(sid: str, layout: dict | None):
    """Make sure we're in WeChat. Returns True if ok."""
    r = _wda_request("GET", f"/session/{sid}/wda/activeAppInfo")
    bundle = r.get("value", {}).get("bundleId", "") if "error" not in r else ""
    if bundle == "com.tencent.xin":
        return True
    wda_launch("微信")
    time.sleep(0.5)
    return True


def _navigate_to_chat(sid: str, contact: str, layout: dict | None) -> tuple[bool, str]:
    """Navigate to a contact's chat. Uses _current_chat to skip if already there."""
    global _current_chat
    if _current_chat == contact:
        return True, f"Already in {contact}'s chat"

    # Tap chat tab to ensure we're on chat list
    if layout:
        tab = layout.get("screens", {}).get("chat_list", {}).get("tab_bar", {}).get("chats", {})
        if tab.get("tap"):
            _tap_cached(sid, tab["tap"][0], tab["tap"][1])
            time.sleep(0.3)

    ok, msg = _tap_text_internal(sid, contact)
    if not ok:
        return False, msg
    time.sleep(0.3)
    _current_chat = contact
    return True, msg


def _get_layout_coords(layout: dict | None) -> tuple[list, list]:
    """Get input field and send button coords from cache, with fallbacks."""
    input_tap = [178, 790]
    send_tap = [344, 757]
    if layout:
        conv = layout.get("screens", {}).get("conversation", {}).get("input_bar", {})
        tf = conv.get("text_field", {})
        if tf.get("tap"):
            input_tap = tf["tap"]
        send = conv.get("more_or_send", {}).get("has_text", {})
        if send.get("tap"):
            send_tap = send["tap"]
    return input_tap, send_tap


@_tool(annotations=_RO)
def wda_wechat_read(contact: str, count: int = 10) -> str:
    """Read recent WeChat messages from a contact. Stays in chat after reading."""
    global _current_chat
    sid = _wda_get_session()
    layout = _load_app_layout("com.tencent.xin")

    already_here = (_current_chat == contact)

    if not already_here:
        _ensure_wechat(sid, layout)
        ok, nav_msg = _navigate_to_chat(sid, contact, layout)
        if not ok:
            return f"Failed to open chat with '{contact}': {nav_msg}"
    else:
        # Already in this chat — dismiss keyboard if open (from prior send)
        _tap_cached(sid, 196, 400)

    import xml.etree.ElementTree as ET
    r = _wda_request("GET", f"/session/{sid}/source")
    if "error" in r:
        return f"Opened {contact}'s chat but failed to read: {r.get('error')}"
    try:
        root = ET.fromstring(r.get("value", "<x/>"))
    except Exception as e:
        return f"XML parse error: {e}"

    texts = []
    noise = {"微信", "返回", "更多", "语音", "表情", "语音输入", "0%", "100%"}
    for elem in root.iter():
        label = elem.attrib.get("label", "").strip()
        value = elem.attrib.get("value", "").strip()
        for t in (label, value):
            if (t and len(t) > 2 and len(t) < 300
                    and t not in noise and t not in texts
                    and "滚动条" not in t and "页栏" not in t):
                texts.append(t)
    _current_chat = contact
    if not texts:
        return f"Opened {contact}'s chat but no messages visible."

    lines = [f"Chat with {contact} ({min(count, len(texts))} messages):"]
    for t in texts[-count:]:
        lines.append(f"  {t[:150]}")
    return "\n".join(lines)


@_tool(annotations=_RW)
def wda_send_wechat(contact: str, text: str, verify: bool = True) -> str:
    """Send a WeChat message. verify=False skips confirmation (faster)."""
    global _current_chat
    sid = _wda_get_session()
    layout = _load_app_layout("com.tencent.xin")

    _ensure_wechat(sid, layout)
    ok, nav_msg = _navigate_to_chat(sid, contact, layout)
    if not ok:
        return f"Failed to open chat with '{contact}': {nav_msg}"

    input_tap, send_tap = _get_layout_coords(layout)

    # Tap input → type → tap send (no sleep — WDA requests are synchronous)
    _tap_cached(sid, input_tap[0], input_tap[1])
    _wda_request("POST", f"/session/{sid}/wda/keys", {"value": list(text)})
    _tap_cached(sid, send_tap[0], send_tap[1])

    if not verify:
        return f"Sent to {contact}: {text}"

    time.sleep(0.3)
    # Verify: one source call — check message sent + read recent messages
    import xml.etree.ElementTree as ET
    r = _wda_request("GET", f"/session/{sid}/source")
    src_text = r.get("value", "") if "error" not in r else ""
    sent_found = text[:30] in src_text
    msgs = []
    if src_text:
        try:
            root = ET.fromstring(src_text)
            for elem in root.iter():
                if elem.attrib.get("type") == "XCUIElementTypeStaticText":
                    label = elem.attrib.get("label", "").strip()
                    if label and len(label) > 1 and len(label) < 200:
                        msgs.append(label)
        except Exception:
            pass

    if sent_found:
        lines = [f"✓ Sent to {contact}: {text}"]
        # Show recent visible text as context (filter out UI noise)
        chat_msgs = [m for m in msgs if len(m) > 3 and m not in ("微信", "返回", "更多", "语音", "表情", "语音输入")]
        if chat_msgs:
            lines.append(f"\nRecent messages:")
            for m in chat_msgs[-8:]:
                lines.append(f"  {m[:120]}")
        return "\n".join(lines)

    # Verification failed — screenshot for debugging
    screenshot_path = ""
    sr = _wda_request("GET", f"/session/{sid}/screenshot")
    if "error" not in sr:
        img = base64.b64decode(sr.get("value", ""))
        screenshot_path = os.path.join(SCREENSHOTS_DIR, f"wda_send_fail_{int(time.time())}.png")
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        with open(screenshot_path, "wb") as f:
            f.write(img)

    _current_chat = None
    return f"⚠ Send may have failed — message not found in chat. Screenshot: {screenshot_path}"


@_tool(annotations=_RO)
def wda_check(detail: bool = False) -> str:
    """See the screen: current app + visible text. detail=True adds device/battery info."""
    sid = _wda_get_session()
    import xml.etree.ElementTree as ET
    lines = []

    if detail:
        r = _wda_request("GET", "/status")
        if "error" not in r:
            v = r.get("value", {})
            lines.append(f"Device: {v.get('os', {}).get('name', '?')} {v.get('os', {}).get('version', '?')}")
            lines.append(f"IP: {v.get('ios', {}).get('ip', '?')}")
        r = _wda_request("GET", f"/session/{sid}/wda/batteryInfo")
        if "error" not in r:
            batt = r.get("value", {})
            level = int(batt.get("level", 0) * 100)
            state = {0: "unknown", 1: "unplugged", 2: "charging", 3: "full"}.get(batt.get("state", 0), "?")
            lines.append(f"Battery: {level}% ({state})")
        r = _wda_request("GET", f"/session/{sid}/window/size")
        if "error" not in r:
            sz = r.get("value", {})
            lines.append(f"Screen: {sz.get('width', '?')}x{sz.get('height', '?')} points")
        lines.append("")

    r = _wda_request("GET", f"/session/{sid}/source")
    if "error" in r:
        return f"Check failed: {r.get('error', 'unknown')}"
    try:
        root = ET.fromstring(r.get("value", "<x/>"))
        app_name = root.attrib.get("name", root.attrib.get("label", "unknown"))
        texts = []
        for elem in root.iter():
            label = elem.attrib.get("label", "").strip()
            value = elem.attrib.get("value", "").strip()
            if label and label not in texts and len(label) < 100:
                texts.append(label)
            if value and value != label and value not in texts and len(value) < 100:
                texts.append(value)
        lines.append(f"App: {app_name}")
        lines.append(f"Visible text ({len(texts)} items):")
        lines.extend(f"  - {t}" for t in texts[:30])
        if len(texts) > 30:
            lines.append(f"  ... and {len(texts) - 30} more")
        return "\n".join(lines)
    except Exception as e:
        return f"Parse error: {e}"


def _scan_ui_structure(root) -> dict:
    """Parse a UI XML tree and extract structural elements: tab bars, nav bars, input fields, buttons."""
    import xml.etree.ElementTree as ET

    def _center(elem):
        x = int(elem.attrib.get("x", 0))
        y = int(elem.attrib.get("y", 0))
        w = int(elem.attrib.get("width", 0))
        h = int(elem.attrib.get("height", 0))
        return [x + w // 2, y + h // 2]

    def _bounds(elem):
        return [int(elem.attrib.get("x", 0)), int(elem.attrib.get("y", 0)),
                int(elem.attrib.get("width", 0)), int(elem.attrib.get("height", 0))]

    result = {"nav_bar": {}, "tab_bar": {}, "buttons": [], "inputs": [], "search_fields": []}

    for elem in root.iter():
        etype = elem.attrib.get("type", "")
        label = elem.attrib.get("label", "").strip()
        name = elem.attrib.get("name", "").strip()

        if etype == "XCUIElementTypeNavigationBar":
            nav = {"bounds": _bounds(elem), "items": {}}
            for child in elem:
                cl = child.attrib.get("label", "").strip() or child.attrib.get("name", "").strip()
                ct = child.attrib.get("type", "")
                if cl:
                    nav["items"][cl] = {"tap": _center(child), "type": ct}
            result["nav_bar"] = nav

        elif etype == "XCUIElementTypeTabBar":
            for child in elem:
                cl = child.attrib.get("label", "").strip()
                if cl:
                    result["tab_bar"][cl] = {"tap": _center(child)}

        elif etype in ("XCUIElementTypeButton", "XCUIElementTypeOther") and label:
            ey = int(elem.attrib.get("y", 0))
            eh = int(elem.attrib.get("height", 0))
            ew = int(elem.attrib.get("width", 0))
            screen_h = int(root.attrib.get("height", 852))
            screen_w = int(root.attrib.get("width", 393))
            # Tab-like: very bottom of screen, small, short label, not scrollbar noise
            is_bottom = ey > screen_h - 60
            is_small = ew < screen_w // 2
            is_short = 1 < len(label) < 8
            is_noise = "滚动" in label
            if is_bottom and is_small and is_short and not is_noise:
                if label not in result["tab_bar"]:
                    result["tab_bar"][label] = {"tap": _center(elem)}
            elif etype == "XCUIElementTypeButton":
                result["buttons"].append({"label": label, "tap": _center(elem)})

        elif etype in ("XCUIElementTypeTextField", "XCUIElementTypeTextView", "XCUIElementTypeSecureTextField"):
            result["inputs"].append({
                "label": label or name or etype.replace("XCUIElementType", ""),
                "tap": _center(elem), "bounds": _bounds(elem)
            })

        elif etype == "XCUIElementTypeSearchField":
            result["search_fields"].append({
                "label": label or name or "search",
                "tap": _center(elem), "bounds": _bounds(elem)
            })

    return result


def _get_source_parsed(sid: str):
    """Get source XML and parse it. Returns (root, error_str)."""
    import xml.etree.ElementTree as ET
    r = _wda_request("GET", f"/session/{sid}/source")
    if "error" in r:
        return None, f"Source failed: {r.get('error')}"
    try:
        return ET.fromstring(r.get("value", "<x/>")), None
    except Exception as e:
        return None, f"XML parse error: {e}"


def _format_layout(layout: dict) -> list[str]:
    """Format a layout dict into human-readable lines."""
    lines = []
    if layout.get("tab_bar"):
        lines.append(f"  Tab bar ({len(layout['tab_bar'])} tabs):")
        for label, info in layout["tab_bar"].items():
            lines.append(f"    {label} → tap({info['tap'][0]}, {info['tap'][1]})")
    if layout.get("nav_bar", {}).get("items"):
        lines.append(f"  Nav bar:")
        for label, info in layout["nav_bar"]["items"].items():
            lines.append(f"    {label} → tap({info['tap'][0]}, {info['tap'][1]})")
    if layout.get("search_fields"):
        for sf in layout["search_fields"]:
            lines.append(f"  Search: {sf['label']} → tap({sf['tap'][0]}, {sf['tap'][1]})")
    if layout.get("inputs"):
        for inp in layout["inputs"]:
            lines.append(f"  Input: {inp['label']} → tap({inp['tap'][0]}, {inp['tap'][1]})")
    return lines


@_tool(annotations=_RO)
def wda_learn_app(name: str = "") -> str:
    """Scan app UI and cache layout. Empty name lists cached layouts."""

    if not name:
        os.makedirs(APP_LAYOUTS_DIR, exist_ok=True)
        files = [f for f in os.listdir(APP_LAYOUTS_DIR) if f.endswith(".json")]
        if not files:
            return "No cached layouts. Call wda_learn_app('AppName') to scan one."
        lines = ["Cached app layouts:"]
        for f in sorted(files):
            with open(os.path.join(APP_LAYOUTS_DIR, f)) as fh:
                d = json.load(fh)
            lines.append(f"  {d.get('app_name', '?')} ({f.replace('.json', '')}) — scanned {d.get('scanned_at', '?')}")
        return "\n".join(lines)

    sid = _wda_get_session()
    wda_launch(name)
    time.sleep(0.5)

    r = _wda_request("GET", f"/session/{sid}/wda/activeAppInfo")
    if "error" in r:
        return f"Cannot get active app: {r.get('error')}"
    app_info = r.get("value", {})
    bundle_id = app_info.get("bundleId") or "unknown"
    app_name = app_info.get("name") or name or "unknown"

    # --- Phase 1: Navigate to main page ---
    back_labels = {"返回", "Back", "back", "关闭", "Close"}
    root, err = _get_source_parsed(sid)
    if not root:
        return err
    screen_w = int(root.attrib.get("width", 393))
    screen_h = int(root.attrib.get("height", 852))
    layout = _scan_ui_structure(root)

    # If tab bar found, tap first tab to go to main page (fastest path)
    if layout["tab_bar"]:
        first_tab = list(layout["tab_bar"].values())[0]
        _tap_cached(sid, first_tab["tap"][0], first_tab["tap"][1])
        time.sleep(0.3)
        root, err = _get_source_parsed(sid)
        if root:
            layout = _scan_ui_structure(root)
    elif any(l in layout.get("nav_bar", {}).get("items", {}) for l in back_labels):
        for label in back_labels:
            info = layout.get("nav_bar", {}).get("items", {}).get(label)
            if info:
                _tap_cached(sid, info["tap"][0], info["tap"][1])
                time.sleep(0.5)
                root, err = _get_source_parsed(sid)
                if root:
                    layout = _scan_ui_structure(root)
                    if layout["tab_bar"]:
                        first_tab = list(layout["tab_bar"].values())[0]
                        _tap_cached(sid, first_tab["tap"][0], first_tab["tap"][1])
                        time.sleep(0.3)
                        root, err = _get_source_parsed(sid)
                        if root:
                            layout = _scan_ui_structure(root)
                break

    main_layout = layout

    # --- Phase 2: Enter first list item for detail page ---
    detail_layout = None
    first_cell = None
    for elem in root.iter():
        if elem.attrib.get("type") == "XCUIElementTypeCell":
            cy = int(elem.attrib.get("y", 0))
            ch = int(elem.attrib.get("height", 0))
            cw = int(elem.attrib.get("width", 0))
            if 90 < cy < screen_h - 100 and ch > 30 and cw > screen_w // 2:
                cx = int(elem.attrib.get("x", 0))
                first_cell = (cx + cw // 2, cy + ch // 2)
                break

    if first_cell:
        _tap_cached(sid, first_cell[0], first_cell[1])
        time.sleep(0.5)
        detail_root, _ = _get_source_parsed(sid)
        if detail_root is not None:
            dl = _scan_ui_structure(detail_root)
            has_back = any(l in back_labels for l in dl.get("nav_bar", {}).get("items", {}))
            if has_back:
                detail_layout = dl
        wda_back()

    # --- Phase 3: Save ---
    layout_data = {
        "app_name": app_name,
        "bundle_id": bundle_id,
        "screen": {"width": screen_w, "height": screen_h},
        "scanned_at": time.strftime("%Y-%m-%d %H:%M"),
        "main_screen": main_layout,
    }
    if detail_layout:
        layout_data["detail_screen"] = detail_layout

    os.makedirs(APP_LAYOUTS_DIR, exist_ok=True)
    path = os.path.join(APP_LAYOUTS_DIR, f"{bundle_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)
        existing.update(layout_data)
    else:
        existing = layout_data
    with open(path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    # --- Format output ---
    lines = [f"Learned {app_name} ({bundle_id})", ""]
    lines.append("Main page:")
    lines.extend(_format_layout(main_layout))
    if detail_layout:
        lines.append("")
        lines.append("Detail page:")
        lines.extend(_format_layout(detail_layout))
    lines.append(f"\nSaved to {path}")
    return "\n".join(lines)


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


@_tool(annotations=_DESTRUCTIVE)
def wda_start() -> str:
    """Start/restart WDA on iPhone."""
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

            tunnel_script = os.path.join(os.path.dirname(__file__), "scripts", "create_tunnel.py")
            subprocess.Popen(
                ["sudo", "-n", "/opt/homebrew/bin/python3.13", tunnel_script,
                 WDA_DEVICE_ID, WDA_TAILSCALE_IP, "49152"],
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


@_tool(annotations=_DESTRUCTIVE)
def wda_renew() -> str:
    """Rebuild WDA to renew 7-day signing (2-3 min)."""
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

    def _public_base(request: Request) -> str:
        override = os.environ.get("WDA_PUBLIC_URL", "").rstrip("/")
        if override:
            return override
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost")
        proto = request.headers.get("x-forwarded-proto", "https")
        return f"{proto}://{host}"

    async def oauth_protected_resource(request: Request):
        base = _public_base(request)
        return JSONResponse({"resource": base, "authorization_servers": [base]})

    async def oauth_metadata(request: Request):
        base = _public_base(request)
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
