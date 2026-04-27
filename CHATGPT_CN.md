# ChatGPT 专用接入路径

这条路径和 Claude / Codex 的 stdio 路径分开。Claude 已经跑通了就继续用原来的配置；这份文档只讲怎么把 wda-mcp 通过 HTTPS 暴露给 ChatGPT Developer Mode。

适用入口：
- ChatGPT 网页版：推荐。
- 手机浏览器打开 `chatgpt.com`：可以试，本质上还是网页版。
- ChatGPT iOS/Android 原生 App：暂时不要当作稳定入口。

## 0. 先盘点现状（1 分钟，省一堆 debug）

动手前先看机器上已经在跑什么。最常见的失败模式是：临时 quick tunnel 和已有 named tunnel 抢同一个端口，路由结果飘忽不定。

```bash
# 8200 端口是不是已经在跑 wda-mcp？
lsof -nP -iTCP:8200 -sTCP:LISTEN

# 是不是已经有 cloudflared named tunnel 在跑？
ps aux | grep '[c]loudflared tunnel run'
cloudflared tunnel list 2>/dev/null
test -f ~/.cloudflared/config.yml && cat ~/.cloudflared/config.yml
```

三种状态：

| 状态 | 你看到什么 | 该怎么做 |
|------|----------|---------|
| **A. 全新机器** | 8200 没东西，没 cloudflared 进程，没 `~/.cloudflared/config.yml` | 从 Step 1 开始，quick tunnel 顺利 |
| **B. server 已经在跑** | 8200 有进程，但没公网 tunnel | 从 Step 3 开始，跳过启 server。先确认那个进程确实是 wda-mcp，不是别的服务占了端口 |
| **C. named tunnel 已经接好** | `cloudflared tunnel run` 在跑，并且 `~/.cloudflared/config.yml` 里已有把某个域名路由到 `localhost:8200` 的规则 | **直接用这个域名。** 跳过 Step 3。已经有 named tunnel 时再起 quick tunnel（`cloudflared tunnel --url …`），两边会读同一份默认配置，路由经常飘忽。直接跳到 Step 4 |

## 1. 生成 OAuth 凭据

HTTP 模式没有 access token 就拒绝启动。一次性配置：

```bash
python scripts/generate_oauth_creds.py
```

会写一份 `~/.wda-oauth.json`（chmod 600），里面是 `client_id`、`client_secret`、`access_token`。`access_token` 是 ChatGPT 要用 `Authorization: Bearer <token>` 发的那个 token。

## 2. 启动 GPT 专用 MCP 服务（端口 8200）

```bash
bash scripts/start_http.sh
```

或直接：

```bash
/opt/homebrew/bin/python3.12 server_chatgpt.py --host 0.0.0.0 --port 8200
```

`server_chatgpt.py` 和 `server.py --http` 共用同一套 OAuth + Bearer 启动器——选一个，**绝对不要两个一起跑**（端口冲突）。

本地 MCP endpoint：

```text
http://localhost:8200/mcp
```

ChatGPT 连不上 localhost，所以要在 Step 3 暴露成 HTTPS。

## 3. 暴露 HTTPS 地址

> 如果你已经有 named tunnel 把固定域名路由到 `localhost:8200`（Step 0 的状态 C），跳过这一步。

### 临时测试（随机 URL，第一次试通用）

```bash
ngrok http 8200
```

或：

```bash
# 如果机器上已有 ~/.cloudflared/config.yml，quick tunnel 默认会读它，
# 容易和 named tunnel 路由打架。加 --config /dev/null 让 quick tunnel
# 用空配置启动。
cloudflared tunnel --config /dev/null --url http://localhost:8200
```

会得到类似 `https://example.trycloudflare.com` 或 `https://abc123.ngrok.io` 的地址。后面加 `/mcp`。这种 URL 每次重启都变。

### 长期使用：固定 URL（推荐）

三选一：

1. **Cloudflare Named Tunnel + 自己的域名**
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create wda-chatgpt
   cloudflared tunnel route dns wda-chatgpt wda-mcp.example.com
   # 用 --url 直接指定，或者在 ~/.cloudflared/config.yml 里加 ingress
   cloudflared tunnel run --url http://localhost:8200 wda-chatgpt
   ```
2. **ngrok 静态 / 预留域名**——在 ngrok 后台配固定域名，转发到 `localhost:8200`。
3. **VPS / 家里固定机器**——把服务挂在自己的 HTTPS 域名后面。

## 4. 上 ChatGPT 之前先 curl 验证一下

两条 curl 能挡掉 90% 的 "ChatGPT 连不上" 问题：

```bash
TOKEN=$(python -c "import json,pathlib; print(json.loads(pathlib.Path('~/.wda-oauth.json').expanduser().read_text())['access_token'])")

# A. 不带 token —— 必须返回 HTTP 401（证明 auth 在生效）
curl -sS -o /dev/null -w "no-auth → HTTP %{http_code}\n" -X POST https://your-host/mcp \
  -H "Accept: application/json, text/event-stream" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# B. 带正确 token —— 必须 200 + SSE 事件列出工具
curl -sS -X POST https://your-host/mcp \
  -H "Accept: application/json, text/event-stream" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify","version":"0"}}}' \
  | head -c 400
```

错误码对照：
- **A 返回 200**：server 在裸奔，**立刻停！** 你正打算把一个无密码的远程操控 URL 交给 ChatGPT。
- **A 返回 502 / 522**：tunnel 通，但 origin 挂了。`lsof -nP -iTCP:8200` 看进程。
- **A 返回 404（Cloudflare 页面）**：tunnel hostname 通，但没有 ingress 把它路由到 `localhost:8200`。检查 `~/.cloudflared/config.yml` 或 `cloudflared tunnel route dns`。
- **B 返回 401**：token 不对。重新读 `~/.wda-oauth.json`，注意末尾别带换行。
- **B 返回 200 + SSE 数据**：✅ 进 Step 5。

## 5. 在 ChatGPT 里创建 App / Connector

1. 在 ChatGPT 网页版打开 Settings → Apps & Connectors。
2. 开启 Developer mode。
3. Create app / Create connector。
4. Connector URL 填公网 HTTPS 的 `/mcp` 地址。
5. 鉴权两选一：
   - **静态 Bearer（最简单）：** 在 connector 的 custom headers 里加 `Authorization: Bearer <access_token>`。token 在 `~/.wda-oauth.json` 里。
   - **OAuth 2.0：** server 已经开放了 `/.well-known/oauth-protected-resource`、`/.well-known/oauth-authorization-server`、`/oauth/authorize`、`/oauth/token`，ChatGPT 会自动走 OAuth 流程引导用户授权。
6. 创建后确认能看到 `wda_check`、`wda_tap`、`wda_type` 等工具。

## 6. 注意权限

server 现在 HTTP 模式没有 access token 就拒绝启动；非回环来源必须带 `Authorization: Bearer <access_token>` 才能调任何工具。完整安全配置看主 README 的[安全章节](README_CN.md#️-安全http-模式的鉴权)。长期固定 URL 建议在 tunnel 前面再叠一层 **Cloudflare Access**——即便 token 泄露，外部还要先过 Access 这关。

`~/.wda-oauth.json` 当密码文件保管（chmod 600），不要 commit。怀疑泄露：`python scripts/generate_oauth_creds.py --force` 重新生成，然后重启 server。

截至 2026-04，OpenAI 文档里 ChatGPT MCP/Apps 仍有 beta 与计划差异：Developer Mode 支持 MCP 工具，但完整写操作权限是否可用要以你账号里的 ChatGPT UI 为准。写操作执行前 ChatGPT 通常会显示确认弹窗。
