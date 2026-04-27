# ChatGPT 专用接入路径

这条路径和 Claude/Codex 的原有 `server.py` 启动方式分开。Claude 已经跑通时继续用原来的配置；ChatGPT 只用这里的 HTTP 入口。

## 1. 启动 GPT 专用 MCP 服务

```bash
/opt/homebrew/bin/python3.12 server_chatgpt.py --host 0.0.0.0 --port 8200
```

本地 MCP endpoint 通常是：

```text
http://localhost:8200/mcp
```

ChatGPT 不能直接连本机地址，所以需要把它暴露成 HTTPS。

## 2. 暴露 HTTPS 地址

临时测试可用 ngrok：

```bash
ngrok http 8200
```

或 Cloudflare Tunnel：

```bash
cloudflared tunnel --url http://localhost:8200
```

把得到的公网 HTTPS 地址后面加 `/mcp`，例如：

```text
https://example.trycloudflare.com/mcp
```

## 3. 在 ChatGPT 里创建 App/Connector

1. 打开 ChatGPT 设置里的 Apps & Connectors。
2. 开启 Developer mode。
3. Create app / Create connector。
4. Connector URL 填公网 HTTPS 的 `/mcp` 地址。
5. 创建后确认能看到 `wda_check`、`wda_tap`、`wda_type` 等工具。

## 4. 注意权限

这个项目有真实写操作：点击、输入、滑动、打开 app。不要把无鉴权的公网 URL 长期开着。临时调试可以用随机 tunnel URL；长期使用建议加 OAuth、Cloudflare Access，或只在可信网络里暴露。

截至 2026-04，OpenAI 文档里 ChatGPT MCP/Apps 仍有 beta 与计划差异：Developer Mode 支持 MCP 工具，但完整写操作权限是否可用要以你账号里的 ChatGPT UI 为准。写操作执行前 ChatGPT 通常会显示确认弹窗。
