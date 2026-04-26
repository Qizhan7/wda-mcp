[中文版 README](README_CN.md)

# WDA MCP — Remote iPhone Control for AI

A standalone [MCP](https://modelcontextprotocol.io) server that lets AI agents control a physical iPhone over the network. Built on Apple's [WebDriverAgent](https://github.com/appium/WebDriverAgent) and optionally [Tailscale](https://tailscale.com) for secure remote access from anywhere — not just your LAN.

Tap buttons, swipe through apps, take screenshots, type text, and inspect UI elements — all through natural language via any MCP-compatible client. Works with **Claude Code** (CLI), **claude.ai** (chat), and **Claude Desktop**.

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
- **Python 3.12+** with `mcp[cli]` installed
- **Python 3.13** (for remote start via Tailscale — the TCP tunnel requires Python 3.13's SSL PSK support)
- **[pymobiledevice3](https://github.com/doronz88/pymobiledevice3)** installed on both Python 3.12 and 3.13
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

> ⚠️ **Manual step required** — this is the one step that cannot be fully automated with a free Apple ID. You must open Xcode and configure signing by hand.

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
        "WDA_DEVICE_ID": "your-device-udid",
        "WDA_BUNDLE_ID": "com.yourname.WebDriverAgentRunner.xctrunner"
      }
    }
  }
}
```

## Remote Access with Tailscale

To control your iPhone from anywhere (not just your local network):

1. Install [Tailscale](https://tailscale.com) on both your Mac and iPhone
2. Note the iPhone's Tailscale IP (e.g. `100.71.146.51`)
3. Set `WDA_TAILSCALE_IP` in your `.env` or MCP config
4. WDA-MCP will try the Tailscale IP first, then fall back to LAN discovery

### 5G / Mobile Data Support

WDA-MCP can start and control WDA even when the iPhone is on mobile data — **no USB, no same network required**. The `wda_start()` tool automatically:

1. Detects the iPhone's RemotePairing service via Tailscale
2. Creates a TCP tunnel using `pymobiledevice3` (requires Python 3.13 + sudo)
3. Launches WDA through the tunnel
4. Auto-patches pymobiledevice3 to fix a [DTX timing issue](https://github.com/doronz88/pymobiledevice3/pull/1665) with RSD tunnels

**Requirements for remote start:**
- iPhone WiFi toggle must be ON (it doesn't need to be connected to any network — just the toggle)
- Tailscale running on both devices
- `sudo` access on the Mac (tunnel creation requires root for the utun interface)
- Python 3.13 with pymobiledevice3: `brew install python@3.13 && python3.13 -m pip install pymobiledevice3`

**Typical workflow:**
1. At home: iPhone on WiFi → `wda_start()` launches WDA via Tailscale tunnel
2. Leave home: iPhone disconnects from WiFi (but toggle stays on) → WDA keeps running
3. On the go: control iPhone via 5G + Tailscale from anywhere

> ### ⚠️ Steps before going out (read carefully!)
>
> **One rule: keep the WiFi button blue (ON). Never turn it off.**
>
> Before leaving home:
> 1. **Connect to WiFi**, confirm WDA is running (you see the automation screen on your phone)
> 2. **Turn on mobile data / 5G**
> 3. **Disconnect from WiFi** — Settings → WiFi → tap current network → "Forget This Network"
> 4. Make sure **no other WiFi will auto-connect** (turn off "Auto-Join" for saved networks)
> 5. Leave! WDA keeps running over 5G + Tailscale
>
> **For daily use it's simpler** — just walk out of WiFi range naturally. As long as you don't manually turn off the WiFi button, WDA stays alive.
>
> ---
>
> **Why? The technical reason:**
>
> | Action | WiFi button | WDA result |
> |--------|-----------|-----------|
> | Disconnect / walk out of range / Control Center tap | 🔵 Blue (ON) | ✅ WDA keeps running |
> | Settings → flip WiFi toggle OFF | ⚪ Grey (OFF) | ❌ WDA killed in ~5 seconds |
>
> iOS treats "WiFi toggle OFF" as a signal to **forcefully terminate all developer processes** including WDA. This is an iOS system-level restriction with no workaround.
>
> As long as the WiFi button is blue — even without connecting to any network — iOS leaves WDA alone.

### Tailscale not connecting on mobile data?

If Tailscale works on WiFi but fails on mobile data (connection times out or gets refused), your carrier network may be blocking the WireGuard protocol that Tailscale uses for direct connections.

**Fix: set up a custom DERP relay server.** DERP is Tailscale's built-in relay — when direct connections are blocked, traffic goes through DERP instead.

1. Deploy a DERP server on any machine reachable from your mobile network (a VPS, or your Mac with port forwarding / Cloudflare Tunnel):
   ```bash
   # On your VPS
   go install tailscale.com/cmd/derper@latest
   derper --hostname=your-derp.example.com --verify-clients
   ```

2. Add it to your Tailscale ACL (in the [admin console](https://login.tailscale.com/admin/acls)):
   ```json
   "derpMap": {
     "Regions": {
       "900": {
         "RegionID": 900,
         "RegionCode": "myrelay",
         "Nodes": [{
           "Name": "my-derp",
           "RegionID": 900,
           "HostName": "your-derp.example.com"
         }]
       }
     }
   }
   ```

3. Optionally disable Tailscale's default DERP servers if they're also blocked — set `"OmitDefaultRegions": true` in the derpMap.

After this, mobile data traffic routes through your DERP server and everything works — WDA remote start, screenshots, control, all of it. No code changes needed.

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

> **Why chat?** Claude Code runs on your computer — it can already control your Mac directly. The magic of WDA-MCP is controlling your *phone* through natural conversation from anywhere. "Hey, take a screenshot of my phone" hits different when you're chatting on the couch.

## Auto-Renewal Cron

Free Apple Developer certificates expire every 7 days. Set up auto-renewal:

```bash
# Add to crontab (runs every 6 days at 3 AM)
crontab -e
0 3 */6 * * cd ~/Desktop/wda-mcp && bash scripts/renew_wda.sh >> /tmp/wda_renew.log 2>&1
```

## VPS Deployment (no Mac needed after initial setup)

Deploy wda-mcp on a VPS. Mac is only needed once to compile WDA.

```
┌──────────┐         ┌──────────────────────────┐         ┌──────────┐
│  Claude  │──HTTP──→│         VPS              │←Tailscale→│  iPhone  │
│(anywhere)│         │  wda-mcp (MCP server)    │          │  WDA     │
└──────────┘         │  pymobiledevice3         │          │  Tailscale│
                     │  Tailscale (exit node)   │          └──────────┘
                     └──────────────────────────┘
```

The VPS handles three roles:
1. **MCP server** — Claude connects here
2. **Tailscale node** — reaches iPhone via Tailscale
3. **Exit node** (optional) — can replace Shadowrocket for users who need VPN + WDA simultaneously

### Setup on VPS

```bash
# Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --advertise-exit-node

# Python 3.13 + wda-mcp
git clone https://github.com/Qizhan7/wda-mcp.git && cd wda-mcp
pip install "mcp[cli]" pymobiledevice3
sudo python3 scripts/patch_pymobiledevice3.py

# Run
WDA_TAILSCALE_IP=<iPhone Tailscale IP> \
WDA_DEVICE_ID=<UDID> \
WDA_BUNDLE_ID=<Bundle ID> \
python server.py --http
```

First-time WDA compilation still requires a Mac + Xcode. After that, VPS handles everything.

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
         └─ Tailscale VPN (anywhere — WiFi, 5G, any network)
```

## Common Pitfalls

### WiFi / Wireless Debugging

> **WDA started via xcodebuild is NOT accessible through the tunnel!** Use `pymobiledevice3 developer dvt xcuitest --rsd` to launch WDA — this exposes WDA's port through the tunnel. xcodebuild launches WDA on the phone's WiFi IP which is not routed through the tunnel.

> **xcuitest connects then drops after ~20 seconds?** You need to patch pymobiledevice3. Run `sudo python3.12 scripts/patch_pymobiledevice3.py`. See [PR #1665](https://github.com/doronz88/pymobiledevice3/pull/1665).

> **Can't create WiFi tunnel with Python 3.12?** iOS 18.2+ removed QUIC. TCP tunnel requires Python 3.13's SSL PSK support. Use Python 3.13 for the tunnel, Python 3.12 for xcuitest.

> **devicectl shows "connecting"?** Restart remoted: `sudo pkill -9 remoted` — wait 5 seconds.

### 5G / Mobile Data

> **WDA dies when WiFi is turned off?** Don't turn off the WiFi **toggle** (Settings → WiFi → grey switch). Just disconnect from the network or walk out of range. WiFi toggle ON + not connected = WDA stays alive.

> **Can't start WDA on 5G?** Correct — iOS only enables RemotePairing when WiFi is connected. Start WDA at home on WiFi, then go out on 5G. WDA keeps running as long as the WiFi toggle stays on.

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
| Build WDA from source | Yes | One-time — borrow a Mac or use GitHub Actions (free macOS runners) |
| Sign WDA | Yes (Xcode) | Re-sign the .ipa on Windows with [Sideloadly](https://sideloadly.io) |
| Install WDA on iPhone | No | `ideviceinstaller`, `go-ios install`, or Sideloadly (all cross-platform) |
| Launch WDA on iPhone | No | [`go-ios runwda`](https://github.com/danielpaulus/go-ios) works on Linux/Windows |
| Control via HTTP | No | Any platform — it's just REST calls to port 8100 |
| 7-day certificate renewal | No | Re-sign with Sideloadly, or pay $99/year for a 1-year certificate |

### Option A: Free — sign with a computer every 7 days

If you already have the WDA `.ipa` file:

1. **Sign and install** using [Sideloadly](https://sideloadly.io) (Windows/Mac) — plug in iPhone via USB, select the .ipa, enter your Apple ID, done
2. **Launch WDA**: use [`go-ios runwda`](https://github.com/danielpaulus/go-ios) via USB
3. **Run this MCP server**: `python server.py` — works anywhere
4. **Every 7 days**: re-sign with Sideloadly (~2 minutes)

> Free Apple ID signing expires every 7 days. Use a computer to re-sign — avoid on-device signing tools as they may trigger Apple ID restrictions.

### Option B: Buy a signing certificate

Purchase a developer or enterprise certificate from a signing service. With a valid certificate you can re-sign the `.ipa` using [zsign](https://github.com/zhlynn/zsign) (cross-platform CLI) or [Sideloadly](https://sideloadly.io), and the signature lasts much longer (typically months to a year).

### Option C: $99/year Apple Developer account — fully automated

With an [Apple Developer account](https://developer.apple.com/programs/), you get a 1-year certificate and API Key access — no 2FA needed in CI, no manual renewal.

1. Fork this repo
2. Add your signing credentials to GitHub repo **Settings → Secrets**:
   - `APPLE_CERTIFICATE_P12` — base64-encoded .p12 certificate
   - `APPLE_CERTIFICATE_PASSWORD` — certificate password
   - `APPLE_PROVISIONING_PROFILE` — base64-encoded .mobileprovision
   - `DEVICE_UDID` — your iPhone's UDID
3. The included workflow (`.github/workflows/renew.yml`) runs every 6 days on GitHub's free macOS runner, builds a fresh WDA, and uploads it to Releases
4. Download and install — or connect your Windows/Linux machine to auto-pull from Releases

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
