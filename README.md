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

## Without a Mac

The main setup guide assumes macOS + Xcode. If you don't have a Mac, here's what you need to know.

### What needs a Mac

| Step | Mac required? | Alternative |
|------|:---:|-------------|
| Build WDA from source | Yes | One-time only — borrow a Mac, use a friend's, or use [GitHub Actions macOS runners](https://docs.github.com/en/actions/using-github-hosted-runners) to compile in CI |
| Sign WDA | Yes (Xcode) | **After first build**: re-sign the .ipa on Windows with [Sideloadly](https://sideloadly.io) |
| Install WDA on iPhone | No | `ideviceinstaller`, `go-ios install`, or Sideloadly (all cross-platform) |
| Launch WDA on iPhone | No | [`go-ios runwda`](https://github.com/danielpaulus/go-ios) works on Linux/Windows |
| Control via HTTP | No | Any platform — it's just REST calls to port 8100 |
| 7-day certificate renewal | No | Re-sign with Sideloadly on Windows, or pay $99/year for a 1-year certificate |

### The practical recipe

1. **One-time on a Mac** (or macOS CI): build WDA with Xcode, save the `.ipa`
2. **On Windows/Linux**: install the `.ipa` with [Sideloadly](https://sideloadly.io) or [`ideviceinstaller`](https://github.com/libimobiledevice/ideviceinstaller)
3. **Launch WDA**: use [`go-ios runwda`](https://github.com/danielpaulus/go-ios) — works on Linux/Windows via USB
4. **Run this MCP server**: `python server.py` — works anywhere
5. **Renewal**: re-sign with Sideloadly every 7 days (free account) or skip renewal entirely with a [$99/year Apple Developer account](https://developer.apple.com/programs/)

### Key tools for non-Mac users

- **[go-ios](https://github.com/danielpaulus/go-ios)** — install apps, launch WDA, forward ports. Linux/Windows/macOS. The strongest cross-platform option.
- **[pymobiledevice3](https://github.com/doronz88/pymobiledevice3)** — device communication, developer disk mounting, port forwarding. Python, all platforms.
- **[Sideloadly](https://sideloadly.io)** — GUI tool for signing and installing IPAs on Windows/macOS. Handles free account re-signing.
- **[ideviceinstaller](https://github.com/libimobiledevice/ideviceinstaller)** — CLI IPA installer for Linux.

> **Bottom line**: You need a Mac exactly once to compile WDA. After that, everything runs on any platform.

## Credits

- [WebDriverAgent](https://github.com/appium/WebDriverAgent) — Facebook/Appium's iOS automation framework
- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) — Python library for iOS device communication
- [Tailscale](https://tailscale.com) — Zero-config mesh VPN
- [Model Context Protocol](https://modelcontextprotocol.io) — Anthropic's open protocol for AI tool use

## Acknowledgments

The idea for this project came from **蛋** and her Claude 蛋壳, who pointed out the pymobiledevice3 + WebDriverAgent approach as the most viable path to iOS remote control — no jailbreak, no third-party auth, just Xcode signing and a bit of patience with Apple's 7-day certificate cycle. Thanks for lighting the way.

## Using with claude.ai (Chat Mode)

The most fun way to use WDA-MCP is through **chat** — talking to Claude naturally and having it control your phone. "Go check my messages", "screenshot my home screen", "open the red app on the second page" — all in conversation.

This requires **HTTP mode** since claude.ai needs to reach your MCP server over the internet.

### Option A: ngrok (quickest, free)

```bash
# Install ngrok
brew install ngrok

# Start MCP server in HTTP mode
python server.py --http --port 8200 &

# Expose to internet
ngrok http 8200
```

ngrok gives you a public URL like `https://abc123.ngrok.io`. Add this as a custom MCP server in claude.ai settings.

### Option B: Cloudflare Tunnel (stable, free, custom domain)

```bash
# Install cloudflared
brew install cloudflare/cloudflare/cloudflared

# Create tunnel (one-time setup)
cloudflared tunnel login
cloudflared tunnel create wda-mcp

# Start MCP server
python server.py --http --port 8200 &

# Expose via tunnel
cloudflared tunnel --url http://localhost:8200
```

For a permanent custom domain, configure the tunnel in your Cloudflare dashboard.

### Adding to claude.ai

1. Go to claude.ai → Settings → MCP Servers
2. Add a new server with your public URL (ngrok or Cloudflare)
3. Set all WDA tools to "Always allow" so you don't have to approve each action

> **Why chat, not Claude Code?** Claude Code runs on your computer — it can already control your Mac directly. The magic of WDA-MCP is controlling your *phone* through natural conversation from anywhere. "Hey, take a screenshot of my phone" hits different when you're chatting on the couch.
