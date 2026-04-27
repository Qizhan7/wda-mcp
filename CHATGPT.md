# ChatGPT-Specific Setup

This path is separate from the Claude / Codex stdio path. If Claude already works on stdio, keep that configuration — this guide only covers exposing wda-mcp over HTTPS for ChatGPT Developer Mode.

Supported entry points:
- ChatGPT web: recommended.
- `chatgpt.com` in a mobile browser: works; it is still the web app.
- ChatGPT iOS/Android native app: **does not work** — OpenAI blocks MCP write actions on native apps. Read-only tools load, but tap/type/swipe are rejected. Use the mobile browser instead.

## Fast path

If you want Steps 0–4 done in one shot:

```bash
bash scripts/prep_for_chatgpt.sh                      # default port 8200
bash scripts/prep_for_chatgpt.sh --url https://your-host/mcp   # also verify public URL
```

The script checks what's running, generates OAuth if missing, starts the server, and verifies both local and public endpoints. On success it prints the connector URL and Bearer token to paste into ChatGPT. If you prefer to walk through each step manually, continue below.

## 0. Take stock first (1 minute, saves a lot of debugging)

Before changing anything, check what is already running on the host. The most common failure mode is a fresh quick-tunnel fighting an existing named-tunnel for the same port.

```bash
# Is :8200 already serving wda-mcp?
lsof -nP -iTCP:8200 -sTCP:LISTEN

# Is a Cloudflare named tunnel already running with wda-mcp routed?
ps aux | grep '[c]loudflared tunnel run'
cloudflared tunnel list 2>/dev/null
test -f ~/.cloudflared/config.yml && cat ~/.cloudflared/config.yml
```

Three possible states:

| State | What you'll see | What to do |
|-------|-----------------|------------|
| **A. Fresh machine** | nothing on 8200, no `cloudflared` process, no `~/.cloudflared/config.yml` | Start at Step 1. Quick tunnels work cleanly. |
| **B. Server already running** | something on 8200, no public tunnel | Start at Step 3 — skip starting the server. Verify the existing process is wda-mcp HTTP, not a stale port collision. |
| **C. Named tunnel already wired** | `cloudflared tunnel run` is up AND `~/.cloudflared/config.yml` already maps a hostname to `localhost:8200` | **Use that hostname.** Skip Step 3 entirely. Starting a `cloudflared tunnel --url …` quick tunnel while a named tunnel is running can yield inconsistent routing because both read the same config defaults. Go to Step 4. |

## 1. Generate OAuth credentials

HTTP mode refuses to start without an access token. One-time setup:

```bash
python scripts/generate_oauth_creds.py
```

This writes `~/.wda-oauth.json` (chmod 600) with `client_id`, `client_secret`, and `access_token`. The access token is what ChatGPT will send as `Authorization: Bearer <token>`.

## 2. Start the GPT MCP server (port 8200)

```bash
bash scripts/start_http.sh
```

Or directly:

```bash
/opt/homebrew/bin/python3.12 server_chatgpt.py --host 0.0.0.0 --port 8200
```

`server_chatgpt.py` and `server.py --http` share the same OAuth + Bearer runner — pick one, never both at the same time (port collision).

Local MCP endpoint:

```text
http://localhost:8200/mcp
```

ChatGPT can't reach localhost; expose it over HTTPS in Step 3.

## 3. Expose an HTTPS URL

> If you already have a named tunnel routing a stable hostname to `localhost:8200` (state C in Step 0), skip this step.

### Quick test (random URL, fine for first try)

```bash
ngrok http 8200
```

or

```bash
# Use --config /dev/null if you have an existing ~/.cloudflared/config.yml that
# would otherwise be read by quick tunnel and confuse routing.
cloudflared tunnel --config /dev/null --url http://localhost:8200
```

You'll get something like `https://example.trycloudflare.com` or `https://abc123.ngrok.io`. Append `/mcp`. The URL changes every restart.

### Stable URL (recommended for daily use)

Pick one:

1. **Cloudflare Named Tunnel + your own domain**
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create wda-chatgpt
   cloudflared tunnel route dns wda-chatgpt wda-mcp.example.com
   # Either pass --url, or add an ingress rule in ~/.cloudflared/config.yml
   cloudflared tunnel run --url http://localhost:8200 wda-chatgpt
   ```
2. **ngrok static / reserved domain** — set the fixed domain in the ngrok dashboard, then forward to `localhost:8200`.
3. **VPS / always-on machine** — serve the ChatGPT MCP endpoint behind your own HTTPS domain.

## 4. Verify the public URL before going to ChatGPT

Two quick curls catch ~90% of "ChatGPT won't connect" problems:

```bash
TOKEN=$(python -c "import json,pathlib; print(json.loads(pathlib.Path('~/.wda-oauth.json').expanduser().read_text())['access_token'])")

# A. Without auth — must return HTTP 401 (proves auth layer is enforcing).
curl -sS -o /dev/null -w "no-auth → HTTP %{http_code}\n" -X POST https://your-host/mcp \
  -H "Accept: application/json, text/event-stream" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# B. With auth — must return HTTP 200 + an SSE event listing tools.
curl -sS -X POST https://your-host/mcp \
  -H "Accept: application/json, text/event-stream" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify","version":"0"}}}' \
  | head -c 400
```

Decode the failure modes:
- **A returns 200**: the server is unauthenticated. Stop. You're about to publish a remote-control URL for your iPhone.
- **A returns 502 / 522**: tunnel is up but origin is down. Check `lsof -nP -iTCP:8200` and the server log.
- **A returns 404 from Cloudflare**: tunnel hostname is up but no ingress rule routes it to `localhost:8200`. Check `~/.cloudflared/config.yml` or `cloudflared tunnel route dns`.
- **B returns 401**: token mismatch. Re-read `~/.wda-oauth.json`, ensure no trailing newline.
- **B returns 200 with SSE data**: ✅ go to Step 5.

## 5. Create the App in ChatGPT

1. Open ChatGPT web Settings → Apps & Connectors.
2. Enable Developer Mode.
3. Create an app / connector.
4. Set the connector URL to the public HTTPS `/mcp` endpoint.
5. Authentication:
   - **Static Bearer token (simplest):** add a custom header `Authorization: Bearer <access_token>`. Token is in `~/.wda-oauth.json`.
   - **OAuth 2.0:** the server exposes `/.well-known/oauth-protected-resource`, `/.well-known/oauth-authorization-server`, `/oauth/authorize`, and `/oauth/token`. ChatGPT will run the discovery flow and prompt the user.
6. Confirm tools like `wda_check`, `wda_tap`, and `wda_type` appear in the connector view.

## 6. Security Notes

The server refuses to start in HTTP mode without an access token, and requires `Authorization: Bearer <access_token>` for every non-loopback request. See the main [Security section](README.md#️-security-http-mode-authentication) for the full setup. For long-lived public URLs, consider layering **Cloudflare Access** in front of the tunnel — even if the access token leaks, Access blocks unenrolled callers.

Treat `~/.wda-oauth.json` like a password file (chmod 600). Never commit it. If you suspect a leak, regenerate with `python scripts/generate_oauth_creds.py --force` and restart.

As of 2026-04, ChatGPT MCP Apps / Developer Mode are still beta. Developer Mode supports MCP tools, but full write access depends on your account and workspace UI. ChatGPT usually shows confirmation dialogs before write actions.
