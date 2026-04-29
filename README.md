[中文版 README](README_CN.md)

# WDA MCP — Remote iPhone Control for AI

A standalone [MCP](https://modelcontextprotocol.io) server that lets AI agents control a physical iPhone over the network. Built on Apple's [WebDriverAgent](https://github.com/appium/WebDriverAgent) and optionally [Tailscale](https://tailscale.com) for secure remote access from anywhere — not just your LAN.

Tap buttons, swipe through apps, take screenshots, type text, and inspect UI elements — all through natural language via any MCP-compatible client.

## Choose Your Route

WDA-MCP needs full read+write MCP support: viewing the screen plus tapping, typing, and swiping. Read-only MCP = can see but can't control.

| You want to use | Entry point | Notes |
|------|------|------|
| **Claude Code / Claude Desktop** | `server.py` stdio | Local MCP, the most stable path. |
| **claude.ai web chat** | `server.py --http` + HTTPS tunnel | Good free chat-based control path. |
| **Codex** | `server.py` stdio | Add `wda` to your Codex MCP config. |
| **ChatGPT web / mobile browser web** | `server_chatgpt.py` + HTTPS `/mcp` | Uses ChatGPT Developer Mode. See [`CHATGPT.md`](CHATGPT.md). |
| **ChatGPT iOS/Android native app** | Not recommended yet | Treat the web version as the stable test path. |

> If Claude already works for you, keep that configuration. ChatGPT has its own `server_chatgpt.py` entry point so the two paths don't get mixed together.

## Platform Compatibility

### Anthropic (Claude)

| Product | Custom MCP? | Read+Write? | Notes |
|---------|:-----------:|:-----------:|------|
| **claude.ai** (web) | ✅ | ✅ | Best low-friction chat entry point. |
| **Claude Desktop** | ✅ | ✅ | Good desktop option. |
| **Claude Code** (CLI) | ✅ | ✅ | Best for development and debugging. |

### OpenAI (ChatGPT / Codex)

| Product | Custom MCP? | Read+Write? | Min. plan | Recommended entry |
|---------|:-----------:|:-----------:|-----------|-------------------|
| **ChatGPT web** | ✅ Developer Mode | ✅ | Plus ($20/mo) | `server_chatgpt.py` + HTTPS `/mcp` |
| **ChatGPT in a mobile browser** | ✅ worth trying | ✅ | Plus | Same as above |
| **ChatGPT native mobile app** | ❌ write blocked | ❌ | — | Use mobile browser (chatgpt.com) instead |
| **Codex CLI / Codex App** | ✅ | ✅ | — | `server.py` stdio |

Custom MCP requires [Developer Mode](https://help.openai.com/en/articles/12584461), available on Plus, Pro, Team, Enterprise, and Edu plans. Free and Go plans cannot add custom MCP servers (Go only gets OpenAI's built-in connectors). With Developer Mode on, all eligible plans get full read+write MCP — no per-plan restriction. Write actions may show a confirmation dialog.

### Other MCP Clients

| Product | Custom MCP? | Read+Write? | Notes |
|---------|:-----------:|:-----------:|------|
| **Gemini CLI** | ✅ | ✅ | Gemini web does not support custom MCP. |
| **Mistral Le Chat** | ✅ | ✅ | Useful free chat entry point to test. |
| **Cursor / Windsurf / Cline** | ✅ | ✅ | Good inside development environments. |

## Tools (22 total, loadable by group)

Tools are organized by usage scenario. Set `WDA_TOOLS` env var to load only the groups you need — saves AI context tokens.

| Group | When | Tools |
|-------|------|-------|
| **`setup`** | First time / maintenance | `wda_status` `wda_start` `wda_renew` |
| **`learn`** | Scan an app's UI once, reuse cached coordinates | `wda_learn_app` |
| **`core`** | Everyday phone control (13 tools) | See below |
| **`wechat`** | Read/send WeChat messages in one call | `wda_wechat_read` `wda_send_wechat` |
| **`util`** | Notifications, clipboard, long press | `wda_long_press` `wda_notifications` `wda_clipboard` |

<details>
<summary><b>Core tools (13)</b> — view, tap, type, navigate</summary>

| Tool | What it does |
|------|-------------|
| `wda_check` | See the screen: app + all visible text. Add `detail=True` for device/battery info |
| `wda_screenshot` | Capture screen as PNG (use `wda_check` first to save tokens) |
| `wda_source` | Full UI element tree as XML |
| `wda_find` | Search elements by text → tap coordinates |
| `wda_tap` | Tap a point (x, y) |
| `wda_tap_text` | Find element by text and tap it (auto-retries 3x) |
| `wda_type` | Type text into focused input |
| `wda_swipe` | Swipe between two points |
| `wda_scroll` | Scroll: `down` / `up` / `left` / `right` |
| `wda_home` | Go to home screen |
| `wda_back` | Go back (iOS edge swipe) |
| `wda_launch` | Open any app via Spotlight |
| `wda_open_url` | Open a URL in Safari |

</details>

### Selective loading

By default all groups are loaded. To reduce token overhead, set `WDA_TOOLS` in your `.env`:

```bash
# Only basic phone control (12 tools)
WDA_TOOLS=core

# Phone control + WeChat (15 tools)
WDA_TOOLS=core,wechat

# Everything (22 tools, default)
# WDA_TOOLS=
```

**Device compatibility:** All coordinates auto-calibrate on first use — works on any iPhone model and iOS version.

### App Layout Learning

Instead of calling `wda_find` every time you interact with an app, scan its layout once and reuse cached coordinates:

```
> Learn WeChat's layout
wda_learn_app("微信")
→ Tab bar: 微信(49,807) 通讯录(147,807) 发现(245,807) 我(343,807)
→ Nav: title(196,75) +(349,75)
→ Search(196,125)
→ Saved to app_layouts/com.tencent.xin.json
```

Cached positions (tab bars, input fields, send buttons) are reused by `wda_send_wechat` and `wda_wechat_read` — dynamic elements like chat list order are still found in real time.

### WeChat Integration

Read and send WeChat messages in a single MCP round-trip:

```
> Read recent messages
wda_wechat_read("Alice", count=10)    # ~6-8s first time, 3s repeat

> Send a message
wda_send_wechat("Alice", "Hello!")    # ~5s with verify

> Read then reply (navigation auto-skipped)
wda_wechat_read("Alice")             # 3s — stays in chat
wda_send_wechat("Alice", "Got it!")  # 5s — skips navigation
```

**Performance** (iPhone → Tailscale → server, measured end-to-end):

| Operation | Time | Notes |
|-----------|------|-------|
| Read (first time) | ~6-8s | Navigate + 1 source call |
| Read (same contact) | **3s** | Already in chat, 1 source call |
| Send (after read) | **5s** | Skip navigation + verify |
| Send (verify=False) | **~2s** | Skip navigation + no verify |
| Read → Send chain | **~8s** | Navigation auto-skipped for send |

The bottleneck is WDA's `source` API (~1.7s per call on iPhone — UI tree traversal). All sleeps between tap/type/send have been removed; WDA requests are synchronous.

- **`_current_chat` state**: after read/send, a follow-up to the same contact skips navigation entirely
- **`verify=False`**: skip post-send source call to save ~3s
- **Screenshot fallback**: if verification fails, a debug screenshot is saved automatically

## Prerequisites

- **macOS** with Xcode installed
- **iPhone** connected via USB (for initial setup) or Tailscale (for remote)
- **Python 3.12+** with `mcp[cli]` installed
- **Python 3.13** (for remote start via Tailscale — the TCP tunnel requires Python 3.13's SSL PSK support)
- **[pymobiledevice3](https://github.com/doronz88/pymobiledevice3)** installed on both Python 3.12 and 3.13
- A free Apple Developer account (for code signing)

## Quick Setup

### 0. Check your environment (optional)

```bash
bash scripts/check.sh                    # without iPhone check
bash scripts/check.sh <TAILSCALE_IP>     # with iPhone connectivity check
```

This verifies Python versions, pymobiledevice3, Tailscale, and optionally iPhone reachability. Fix anything marked ❌ before continuing.

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

Claude and Codex use the original `server.py` entry point:

```bash
# stdio mode (for Claude Code / MCP clients)
python server.py

# HTTP mode (port 8200)
python server.py --http
```

ChatGPT uses the dedicated `server_chatgpt.py` entry point in [`CHATGPT.md`](CHATGPT.md).

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

### 7. Add to Codex

Codex reads MCP servers from `~/.codex/config.toml`. If your `python` is not Python 3.12+, set `command` to your full Python 3.12 path.

```toml
[mcp_servers.wda]
command = "python3.12"
args = ["/path/to/wda-mcp/server.py"]
cwd = "/path/to/wda-mcp"
startup_timeout_sec = 20
tool_timeout_sec = 300
```

Restart Codex, then check `/mcp` or `codex mcp list`.

## Stage 1: USB Local Validation

**Goal:** Prove WDA itself works: signing, certificates, UDID, Bundle ID, Xcode build, and WDA launch. Do not debug AP isolation, Tailscale, or 5G yet.

**Pass criteria:** the automation screen appears on the iPhone. If the Mac and iPhone are also on the same WiFi, `wda_status` and `wda_screenshot` return normally.

1. Connect iPhone to the Mac over USB and keep it unlocked. The phone may stay on home WiFi, but do not unplug USB during this stage.
2. Confirm the iPhone trusts the computer and the developer certificate under **Settings → General → VPN & Device Management**.
3. Fill `.env` with `WDA_DEVICE_ID`, `WDA_BUNDLE_ID`, and `WDA_PROJECT_DIR`; `WDA_TAILSCALE_IP` can stay empty for now.
4. Start the MCP server and call `wda_start()`, or run `WebDriverAgentRunner` directly in Xcode.
5. When the automation screen appears on the iPhone, WDA itself has passed the first gate. If the Mac and iPhone are also on the same WiFi, you can also test `wda_status` and `wda_screenshot`.

**If stuck, check:**
- The iPhone trusts the computer and developer certificate.
- `WDA_DEVICE_ID`, `WDA_BUNDLE_ID`, and `WDA_PROJECT_DIR` are correct.
- WDA builds in Xcode, and the Bundle ID matches the signing profile.
- The phone is unlocked, Auto-Lock is disabled, and `remoted` is not stuck.

If USB validation fails, do not debug WiFi/5G yet.

## Stage 2: USB → WiFi Handoff Checklist

**Goal:** Move from "WDA launches over USB" to "after unplugging USB, the Mac can still reach the iPhone over the same WiFi." Many first-time setups fail here, so only debug LAN reachability and Xcode wireless pairing at this stage.

**Pass criteria:** **Connect via network** is enabled in Xcode; after unplugging USB, the Mac can `ping <iPhone WiFi IP>` and `curl http://<iPhone WiFi IP>:8100/status` returns WDA status.

Keep these three checks separate:

| Goal | What you are testing | Common causes of failure |
|------|----------------------|--------------------------|
| **LAN direct access** | Mac can reach `http://<iPhone WiFi IP>:8100/status` | Different subnet, guest WiFi, AP/client isolation, dual-homed Mac/wrong route, VPN/proxy routing |
| **Tailscale access** | Mac can reach `http://<iPhone Tailscale IP>:8100/status` | iPhone Tailscale offline, another VPN taking over, UDP blocked |
| **Wireless WDA launch** | Mac can reach the iPhone RemotePairing port `49152` | Xcode network pairing not done, Tailscale/network handoff interrupted, locked phone, stuck `remoted` |

Do not unplug USB and leave immediately. Validate this at home first:

1. Keep USB connected and confirm WDA is running on the iPhone.
2. Put Mac and iPhone on the same normal WiFi / same router. Avoid guest, campus, hotel, or isolated office networks. If the Mac is on Ethernet and WiFi at the same time, temporarily disconnect the unrelated network.
3. In Xcode, open Window → Devices and Simulators → select iPhone → enable **Connect via network**. Apple's [wireless device pairing guide](https://help.apple.com/xcode/mac/current/en.lproj/devbc48d1bad.html) pairs over USB first, then disconnects the cable.
4. Find the iPhone WiFi IP in Settings → WiFi → current network `i`.
5. Test LAN direct access from the Mac:
   ```bash
   ping <iPhone WiFi IP>
   route -n get <iPhone WiFi IP> | grep -E 'interface|gateway|source'
   curl -m 3 http://<iPhone WiFi IP>:8100/status
   ```
6. If using Tailscale, test that path too:
   ```bash
   tailscale status
   tailscale ping <iPhone Tailscale IP>
   curl -m 3 http://<iPhone Tailscale IP>:8100/status
   ```
7. If you need to start/restart WDA wirelessly, test RemotePairing:
   ```bash
   python3.12 - <<'PY'
   import socket
   ip = "<iPhone Tailscale IP or WiFi IP>"
   s = socket.socket()
   s.settimeout(3)
   s.connect((ip, 49152))
   print("RemotePairing OK")
   PY
   ```

Apple's [wireless device troubleshooting guide](https://help.apple.com/xcode/mac/current/en.lproj/devac3261a70.html) also recommends confirming the device is paired, Mac and device are on the same network, and `ping <device IP>` works.

**If stuck, check:**
- Mac and iPhone are on the same normal WiFi / same router, not guest, campus, hotel, or isolated office WiFi.
- If `ping <iPhone WiFi IP>` fails, suspect different subnets, AP/client isolation, or a dual-homed Mac using the wrong route.
- If the Mac is on Ethernet and WiFi at the same time, temporarily disconnect the unrelated network and test again.
- Xcode really completed **Connect via network**; if unsure, pair over USB again.
- `curl :8100` only proves you can reach an already-running WDA. Wireless start/restart also needs `49152`.

## Stage 3: WiFi / LAN Usage First

**Goal:** Let Claude/Codex/MCP reliably control the iPhone on the same WiFi/router. 5G and VPS both build on this layer.

**Pass criteria:** `curl http://<iPhone WiFi IP>:8100/status` reliably returns WDA status, and `wda_status` / `wda_screenshot` work.

1. Put iPhone on WiFi and Mac on the same WiFi/router.
2. Start WDA over USB or Xcode and wait until the automation screen appears on the iPhone.
3. Find the iPhone WiFi IP in Settings → WiFi → current network `i`.
4. From the Mac, confirm WDA is reachable:
   ```bash
   ping <iPhone WiFi IP>
   curl -m 3 http://<iPhone WiFi IP>:8100/status
   ```
5. Once `curl` returns WDA status, Claude/Codex/MCP can control the phone through that WiFi IP.

**If stuck, check:**
- Same subnet and same normal SSID; do not use guest WiFi.
- AP isolation / client isolation / device-to-device blocking in router settings.
- Mac connected to Ethernet plus another WiFi, causing the wrong route to the iPhone IP.
- A global proxy stealing LAN routes; LAN ranges should go DIRECT.

If this step fails, do not debug 5G yet.

## Stage 4: Remote Access with Tailscale

**Goal:** Control your iPhone from anywhere, not just the local network.

**Pass criteria:** `tailscale status` shows the iPhone online, `tailscale ping <iPhone Tailscale IP>` succeeds, and `curl http://<iPhone Tailscale IP>:8100/status` returns WDA status.

1. Install [Tailscale](https://tailscale.com) on both your Mac and iPhone
2. Note the iPhone's Tailscale IP (e.g. `100.x.x.x` from the `100.64.0.0/10` CGNAT range)
3. Set `WDA_TAILSCALE_IP` in your `.env` or MCP config
4. WDA-MCP will try the Tailscale IP first. If that fails, it reads the WDA URL from `/tmp/wda_run.log` and tries a few common LAN IPs. For first-time setup, explicitly setting `WDA_TAILSCALE_IP` is more reliable

**If stuck, check:**
- Tailscale is online on the iPhone; enable **VPN On Demand / Connect On Demand** if it drops in the background.
- Other iPhone VPN/proxy apps are not running at the same time. Test with only Tailscale enabled.
- Mac proxy/VPN rules are not stealing `100.64.0.0/10` Tailscale routes.
- `WDA_TAILSCALE_IP` is the iPhone's Tailscale IP, not the Mac/VPS IP.
- If Tailscale ping works but `8100` does not, WDA may not be running; go back to the WiFi stage and start WDA first.

## Stage 5: 5G / Mobile Data Support

**Goal:** After the iPhone leaves WiFi, keep controlling the already-running WDA over 5G + Tailscale. If `49152` is reachable, then try remote start/restart.

**Pass criteria:** after switching to mobile data, `tailscale ping <iPhone Tailscale IP>` and `curl http://<iPhone Tailscale IP>:8100/status` still work. `49152` reachability is a bonus: it means remote start/restart may work.

WDA-MCP can control WDA while the iPhone is on mobile data — **no USB, no same LAN required**. Starting/restarting WDA depends on the iPhone RemotePairing service; the real test is whether port `49152` is reachable on the iPhone Tailscale IP, not whether the phone currently says WiFi or 5G. When RemotePairing port `49152` is reachable, `wda_start()` automatically:

Cellular remote start can still fail because of carrier networking, Tailscale reconnects, DERP/UDP limitations, VPN/proxy conflicts, or WiFi -> cellular handoff jitter. If `49152` is unreachable or WDA is unstable after trying, go back to the WiFi/LAN workflow above, start WDA on WiFi first, then use the important workflow below to switch to 5G and keep controlling it.

1. Detects the iPhone's RemotePairing service via Tailscale
2. Creates a TCP tunnel using `pymobiledevice3` (requires Python 3.13 + sudo)
3. Launches WDA through the tunnel
4. Checks whether pymobiledevice3 includes the [DTX timing fix](https://github.com/doronz88/pymobiledevice3/pull/1665), and applies the local compatibility patch if an older install is missing it

**Requirements for remote start/restart:**
- iPhone is paired in Xcode with **Connect via network**
- RemotePairing port `49152` is reachable on the iPhone Tailscale IP
- Keep the iPhone WiFi toggle ON. It does not have to be connected to a WiFi network, but do not turn the WiFi toggle off
- If `49152` disappears after switching to cellular, start WDA on WiFi first, then leave WiFi and keep controlling it
- Tailscale running on both devices
- `sudo` access on the Mac (tunnel creation requires root for the utun interface)
- Python 3.13 with pymobiledevice3: `brew install python@3.13 && python3.13 -m pip install pymobiledevice3`

**Typical workflow:**
1. At home: iPhone on WiFi → `wda_start()` launches WDA via Tailscale tunnel
2. Before leaving: "Forget This Network" to disconnect WiFi cleanly → iPhone switches to 5G instantly → WDA stays alive
3. On the go: control iPhone via 5G + Tailscale from anywhere; if `49152` remains reachable, remote restart can work too

**If stuck, check:**
- The WiFi toggle is still ON. Do not turn off the main WiFi switch in Settings.
- If `8100` drops, check Tailscale, mobile carrier networking, DERP, and VPN/proxy conflicts.
- If `8100` stays up but `49152` drops, you can still control the running WDA but cannot restart it remotely yet. Starting on WiFi is the stable fallback.
- If it drops during handoff, use the watcher below to see whether `ping`, `8100`, or `49152` fails first.
- If 5G remains unstable, stop digging and use the WiFi start-and-keepalive workflow.

> ### ⚠️ Important workflow before going out (read carefully!)
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
> This tested flow is the key to keeping WDA alive on 5G. Do not skip steps.
>
> **For daily use, still do the "Forget" step.** Walking out of WiFi range naturally does NOT reliably keep WDA alive — the iPhone holds onto weak WiFi signal too long, causing the TCP tunnel to time out before switching to 5G. "Forget This Network" is instant and lets iOS cut over to 5G cleanly.
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

## Advanced Troubleshooting: Ports, Scripts, Networks

This section is for cross-stage debugging. First-time users should follow the 5 stages above, then come here only for the item that matches the failure.

### Know the two ports

- `8100`: WDA HTTP service. If this works, you can control an already-running WDA: screenshot, tap, type, inspect UI.
- `49152`: iPhone RemotePairing service. This is needed for wireless start/restart.
- **WDA access is not the same as WDA launch.** On 5G, if `8100` works but `49152` does not, you can usually keep controlling the running WDA but cannot restart it remotely yet.

### Diagnose USB/WiFi/Tailscale

```bash
bash scripts/diagnose_usb_wifi.sh <iPhone WiFi IP> <iPhone Tailscale IP>
```

When helping someone remotely, ask for the full diagnostic output, especially `Mac local IPs`, `Mac network snapshot`, `Mac route to iPhone WiFi IP`, `LAN ping`, `WiFi WDA status`, and `Tailscale ping`. Also ask whether the Mac is connected to Ethernet and WiFi at the same time, and which router/SSID the iPhone is actually using.

If the failure happens during WiFi -> cellular handoff, run a watcher from the Mac or VPS:

```bash
bash scripts/watch_handoff.sh <iPhone Tailscale IP>
```

Interpret the first failing column: `ping` means Tailscale/network handoff, `8100` means WDA access dropped, and only `49152` failing means you can still control the running WDA but cannot restart it yet.

### Restricted network notes

- AP/client isolation is common on guest, campus, hotel, and some ISP/router default WiFi networks. Symptom: both devices have internet, but `ping <iPhone WiFi IP>` fails.
- Do not use guest WiFi for the first setup. Use a normal home/private SSID or a travel router with client isolation off.
- 2.4 GHz / 5 GHz networks, mesh networks, or two routers may be on different subnets. Check whether Mac and iPhone IPs look like the same subnet, for example `192.168.1.x` and `192.168.1.y`.
- A Mac connected to both Ethernet and WiFi can route traffic through the wrong network. Example: Ethernet on router A, WiFi on router B, iPhone on router B. Use `route -n get <iPhone WiFi IP>` and check `interface` / `source address`; if it points to the wrong network, unplug Ethernet, disable the unrelated WiFi, or change network service order before testing again.
- Other iPhone VPN/proxy apps can conflict with Tailscale. Tailscale's own docs note that iOS usually only supports one active VPN at a time, and another VPN may drop Tailscale traffic. Test with only Tailscale enabled. If you need a proxy, prefer a Tailscale exit node. See [Tailscale + other VPNs](https://tailscale.com/docs/reference/faq/other-vpns).
- Mac global proxy/VPN rules should bypass LAN and Tailscale ranges: `192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`, and `100.64.0.0/10`.

### pymobiledevice3 / tunnel pitfalls

> **WDA started via xcodebuild is NOT accessible through the tunnel!**
>
> `xcodebuild` launches WDA on the phone's WiFi IP, for example `192.168.1.14:8100`, but that port is not routed through the pymobiledevice3 tunnel. To expose WDA through the tunnel, use:
> ```bash
> python3.12 -m pymobiledevice3 developer dvt xcuitest --rsd <tunnel-address> <port> <BundleID>
> ```

> **xcuitest connects then drops after ~20 seconds?**
>
> Older pymobiledevice3 releases need the DTX fix from [PR #1665](https://github.com/doronz88/pymobiledevice3/pull/1665). The PR is merged to upstream master, but PyPI may lag. Run the compatibility patch only if your installed version is missing the fix:
> ```bash
> sudo python3.12 scripts/patch_pymobiledevice3.py
> ```
> The script is safe to re-run and no-ops when the fix is already present.

> **Can't create a WiFi tunnel with Python 3.12?**
>
> iOS 18.2+ removed QUIC. TCP tunnel requires Python 3.13's SSL PSK support. Use Python 3.13 for the tunnel and Python 3.12 for xcuitest.

> **devicectl shows "connecting"?**
>
> Restart `remoted`:
> ```bash
> sudo pkill -9 remoted
> # Wait 5 seconds; the device should become "available (paired)"
> ```

## ⚠️ Security: HTTP Mode Authentication

The local stdio path used by Claude Code / Codex never opens a port — it is safe. The risk is HTTP mode (`server.py --http` / `server_chatgpt.py`), which exposes real write actions: tap, type, screenshot, read clipboard, open any app. **Do not run HTTP mode unauthenticated on a public URL.**

The server now ships with built-in **OAuth 2.0 + Bearer** authentication. HTTP mode **refuses to start without an access token.**

### One-time setup

```bash
python scripts/generate_oauth_creds.py
```

This writes `~/.wda-oauth.json` (chmod 600) with a random `client_id`, `client_secret`, and `access_token`. The access token is the Bearer header your MCP clients send. Treat it like a password.

### Start HTTP mode

```bash
bash scripts/start_http.sh
```

Or directly (foreground):

```bash
python server.py --http
```

The runner reads `~/.wda-oauth.json` (or `WDA_OAUTH_*` env vars), starts uvicorn on `0.0.0.0:8200`, and exposes:

- `/mcp` — the MCP endpoint. Requires `Authorization: Bearer <access_token>` from non-loopback clients.
- `/.well-known/oauth-protected-resource`, `/.well-known/oauth-authorization-server` — OAuth discovery.
- `/oauth/authorize`, `/oauth/token` — full OAuth 2.0 flow (`authorization_code` and `client_credentials`) for MCP clients that prefer enrollment over a static Bearer token.

Loopback clients (`127.0.0.1`, `::1`) are allowed without auth so a local agent on the same machine can connect over `http://localhost:8200/mcp` without needing the token.

### Connecting MCP clients

| Client | How to authenticate |
|--------|---------------------|
| **claude.ai custom connector** | Paste `Authorization: Bearer <access_token>` as a custom header |
| **ChatGPT Developer Mode** | Paste the token, or let it run the OAuth `authorization_code` flow |
| **curl / scripts** | `curl -H "Authorization: Bearer $TOKEN" https://your-url/mcp` |
| **Local Claude Code via stdio** | No token needed — stdio bypasses HTTP entirely |

### Defense in depth (recommended for stable public URLs)

For a domain you keep online long-term, layer Cloudflare Access in front of the tunnel:

1. Cloudflare Zero Trust → Access → Applications → Add self-hosted application
2. Application domain = your tunnel hostname (e.g. `wda-mcp.example.com`)
3. Add a policy, e.g. `Include → Emails → your@email.com`, or GitHub / Google login

Even if your access token leaks, callers still need to clear Cloudflare Access first. ChatGPT/Claude.ai connectors can use Cloudflare Access **Service Tokens** (set as a header) for non-interactive auth.

### Always

- Treat ngrok / `*.trycloudflare.com` URLs as **temporary testing only**. Stop the tunnel when done.
- Never commit `~/.wda-oauth.json` or paste the access token into screenshots, chats, issues, or git.
- If you suspect a leak: regenerate with `python scripts/generate_oauth_creds.py --force`, restart the server.
- Do not weaken the runner (e.g. removing the `access_token` check) just to "make it work" with a misconfigured client. Fix the client.

## Using with claude.ai (Chat Mode)

> ⚠️ Before exposing anything publicly, complete the [Security setup](#️-security-http-mode-authentication) above (`generate_oauth_creds.py` + `start_http.sh`). The flow below covers how to expose port `8200`; the server enforces Bearer auth on top.

The most fun way to use WDA-MCP is through **chat** — talking to Claude naturally and having it control your phone. "Go check my messages", "screenshot my home screen", "open the red app on the second page" — all in conversation.

This requires **HTTP mode** since claude.ai needs to reach your MCP server over the internet.

### Option A: ngrok (quickest, free)

```bash
# Install ngrok
brew install ngrok

# Start MCP server in HTTP mode
python server.py --http &

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
python server.py --http &

# Expose via tunnel
cloudflared tunnel --url http://localhost:8200
```

For a permanent custom domain, configure the tunnel in your Cloudflare dashboard.

### Adding to claude.ai

1. Go to claude.ai → Settings → Connectors → **Add custom connector**
2. **Name:** anything you like (e.g. `WDA`)
3. **URL:** your public HTTPS URL with `/mcp` (e.g. `https://your-host/mcp`)
4. Expand **Advanced settings**:
   - **OAuth Client ID:** from `~/.wda-oauth.json`
   - **OAuth Client Secret:** from `~/.wda-oauth.json`
5. Click **Add** — Claude.ai will auto-discover the OAuth endpoints and complete the handshake
6. Set all WDA tools to "Always allow" so you don't have to approve each action

```bash
# Print your Client ID and Secret
python3 -c "import json,pathlib; d=json.loads(pathlib.Path('~/.wda-oauth.json').expanduser().read_text()); print(f'Client ID:     {d[\"client_id\"]}'); print(f'Client Secret: {d[\"client_secret\"]}')"
```

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
3. **Exit node** (optional) — can replace an extra VPN/proxy path to reduce VPN conflicts

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
A: Yes, but the Mac must be able to reach the iPhone WiFi IP. If needed, find `ServerURLHere` in `/tmp/wda_run.log`; automatic IP guessing is only a fallback. Tailscale just adds remote access.

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
