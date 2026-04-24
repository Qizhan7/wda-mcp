# WDA MCP — Remote iPhone Control for AI

A standalone [MCP](https://modelcontextprotocol.io) server that lets AI agents control a physical iPhone over the network. Built on Apple's [WebDriverAgent](https://github.com/appium/WebDriverAgent) and optionally [Tailscale](https://tailscale.com) for secure remote access from anywhere — not just your LAN.

Tap buttons, swipe through apps, take screenshots, type text, and inspect UI elements — all through natural language via any MCP-compatible client (Claude Code, Claude Desktop, etc.).

## Tools

| Tool | Description |
|------|-------------|
| `wda_status` | Check if WDA is running. Returns iOS version, IP, ready state |
| `wda_screenshot` | Capture the iPhone screen. Returns the saved PNG path |
| `wda_tap` | Tap a point on screen (x, y in points) |
| `wda_swipe` | Swipe between two points with configurable duration |
| `wda_type` | Type text into the focused input field |
| `wda_home` | Swipe up to go to the home screen (Face ID devices) |
| `wda_source` | Get the UI element tree (XML with labels and coordinates) |
| `wda_start` | Start or restart the WDA process on the iPhone |
| `wda_renew` | Rebuild WDA to renew the 7-day free signing certificate |

## Prerequisites

- **macOS** with Xcode installed
- **iPhone** connected via USB (for initial setup) or Tailscale (for remote)
- **Python 3.10+** with `mcp[cli]` installed
- A free Apple Developer account (for code signing)

## Quick Setup

### 1. Install dependencies

```bash
pip install "mcp[cli]"
brew install pymobiledevice3  # optional, for device discovery
```

### 2. Clone and build WebDriverAgent

```bash
git clone https://github.com/appium/WebDriverAgent.git ~/Desktop/WebDriverAgent
cd ~/Desktop/WebDriverAgent
```

Open `WebDriverAgent.xcodeproj` in Xcode:
- Select the **WebDriverAgentRunner** target
- Under **Signing & Capabilities**, choose your Apple ID team
- Set a unique **Bundle Identifier** (e.g. `com.yourname.WebDriverAgentRunner`)
- Build for your connected device:

```bash
xcodebuild build-for-testing \
    -project WebDriverAgent.xcodeproj \
    -scheme WebDriverAgentRunner \
    -destination "id=$(xcrun xctrace list devices | grep iPhone | head -1 | grep -oE '[A-F0-9-]{25,}')" \
    -allowProvisioningUpdates
```

### 3. Trust the certificate on iPhone

Go to **Settings → General → VPN & Device Management** and trust the developer certificate.

### 4. Configure environment

```bash
cp config.example.env .env
# Edit .env with your device UDID and Tailscale IP
```

Find your device UDID:
```bash
xcrun xctrace list devices
```

### 5. Run the server

```bash
# stdio mode (for Claude Code / MCP clients)
python server.py

# HTTP mode (port 8200)
python server.py --http
```

### 6. Add to Claude Code

Add to your `.mcp.json`:
```json
{
  "mcpServers": {
    "wda": {
      "command": "python",
      "args": ["/path/to/wda-mcp/server.py"],
      "env": {
        "WDA_TAILSCALE_IP": "100.x.x.x",
        "WDA_DEVICE_ID": "your-device-udid"
      }
    }
  }
}
```

## Remote Access with Tailscale

To control your iPhone from anywhere (not just your local network):

1. Install [Tailscale](https://tailscale.com) on both your Mac and iPhone
2. Note the iPhone's Tailscale IP (e.g. `100.71.146.51`)
3. Set `WDA_TAILSCALE_IP` in your `.env`
4. WDA-MCP will try the Tailscale IP first, then fall back to LAN discovery

This means the AI can control the phone even when it's on mobile data — no port forwarding needed.

## Auto-Renewal Cron

Free Apple Developer certificates expire every 7 days. Set up auto-renewal:

```bash
# Add to crontab (runs every 6 days at 3 AM)
crontab -e
0 3 */6 * * cd ~/Desktop/wda-mcp && bash scripts/renew_wda.sh >> /tmp/wda_renew.log 2>&1
```

## Architecture

```
┌──────────────────┐     MCP (stdio/HTTP)     ┌──────────────────┐
│   AI Agent       │◄────────────────────────►│   wda-mcp        │
│ (Claude Code)    │                          │   server.py      │
└──────────────────┘                          └────────┬─────────┘
                                                       │ HTTP :8100
                                              ┌────────▼─────────┐
                                              │  WebDriverAgent  │
                                              │  (on iPhone)     │
                                              └────────┬─────────┘
                                                       │
                                              ┌────────▼─────────┐
                                              │  iPhone Screen   │
                                              │  tap/swipe/type  │
                                              └──────────────────┘

         Network options:
         ├─ USB (local only)
         ├─ LAN Wi-Fi (same network)
         └─ Tailscale (anywhere with internet)
```

## FAQ

**Q: Do I need a paid Apple Developer account?**
A: No. A free account works, but you'll need to re-sign every 7 days (use `wda_renew` or the cron script).

**Q: What iPhone models are supported?**
A: Any iPhone that supports WebDriverAgent — generally iPhone 6s and later on a compatible iOS version.

**Q: The screenshot coordinates don't match what I see?**
A: WDA uses **points**, not pixels. iPhone 14 Pro is 393×852 points. Use `wda_source` to get exact element coordinates.

**Q: WDA keeps disconnecting?**
A: Make sure the iPhone doesn't auto-lock. Go to Settings → Display & Brightness → Auto-Lock → Never (at least during use).

**Q: Can I use this without Tailscale?**
A: Yes. WDA-MCP falls back to LAN IP discovery and the WDA log file. Tailscale just adds remote access.

## Credits

- [WebDriverAgent](https://github.com/appium/WebDriverAgent) — Facebook/Appium's iOS automation framework
- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) — Python library for iOS device communication
- [Tailscale](https://tailscale.com) — Zero-config mesh VPN
- [Model Context Protocol](https://modelcontextprotocol.io) — Anthropic's open protocol for AI tool use
