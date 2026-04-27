[English README](README.md)

# WDA MCP — 用 AI 远程控制 iPhone

一个独立的 [MCP](https://modelcontextprotocol.io) 服务器，让 AI 通过网络控制你的 iPhone。基于 Apple 的 [WebDriverAgent](https://github.com/appium/WebDriverAgent)，配合 [Tailscale](https://tailscale.com) 实现从任何地方远程控制——不限于局域网。

点击按钮、滑动屏幕、截图、输入文字、查看 UI 元素——全部通过自然语言完成。

## 平台兼容性

WDA-MCP 需要支持**读+写**的 MCP（能看屏幕也能操控）。只读 MCP = 能看不能点。

### Anthropic（Claude）

| 产品 | 自定义 MCP？ | 能操控？ | 最低计划 | 费用 |
|------|:----------:|:------:|---------|------|
| **claude.ai**（网页） | ✅ | ✅ | 免费（1 个连接器） | $0 |
| **Claude Desktop** | ✅ | ✅ | 免费 | $0 |
| **Claude Code**（命令行） | ✅ | ✅ | Pro 或 API | ~$20/月 |

最佳免费选择。免费版 claude.ai 就能加 1 个自定义 MCP 连接器，完整操控。

### OpenAI（ChatGPT）

| 产品 | 自定义 MCP？ | 能操控？ | 最低计划 | 费用 |
|------|:----------:|:------:|---------|------|
| **ChatGPT**（网页/桌面/手机） | ✅ | ✅ | Plus | $20/月 |
| **ChatGPT** 免费/Go | ❌ | — | — | — |
| **Codex CLI** | ✅ | ✅ | API | 按量付费 |

开启方式：设置 → Apps → Advanced → Developer Mode。自定义 MCP 在 Plus/Pro/Business/Enterprise 上都支持完整读写。需要 HTTPS（用 ngrok/Cloudflare 暴露）。写操作会弹确认框。注意：OpenAI **内置**连接器（Notion、Drive 等）是只读的——这个限制不影响 wda-mcp 这种自定义 MCP。

### Google（Gemini）

| 产品 | 自定义 MCP？ | 能操控？ | 最低计划 | 费用 |
|------|:----------:|:------:|---------|------|
| **Gemini CLI** | ✅ | ✅ | 免费 Google 账号 | $0 |
| **Gemini 网页版** | ❌ | — | — | 不支持 |
| **Gemini Enterprise** | ✅ | ✅ | Cloud 付费 | $$$ |

Gemini CLI 免费且功能完整。网页版（免费或 Advanced $20/月）不支持自定义 MCP。

### 其他

| 产品 | 自定义 MCP？ | 能操控？ | 最低计划 | 费用 |
|------|:----------:|:------:|---------|------|
| **Mistral Le Chat** | ✅ | ✅ | 免费 | $0 |
| **Cursor** | ✅ | ✅ | Pro | $20/月 |
| **Windsurf** | ✅ | ✅ | 免费 | $0 |
| **Cline**（VS Code） | ✅ | ✅ | 免费（需 LLM API） | $0 + API |
| **VS Code + Copilot** | ✅ | ✅ | Copilot 订阅 | $10/月 |

### 按预算推荐

| 预算 | 推荐 |
|------|------|
| **免费** | claude.ai（1个连接器）、Gemini CLI、Mistral Le Chat |
| **$20/月** | Claude Pro、ChatGPT Plus、Cursor Pro |
| **全部功能** | Claude Max、Claude Code |

## 工具列表

| 工具 | 功能 |
|------|------|
| **查看** | |
| `wda_check` | 首选查看方式——返回当前 app + 屏幕所有文字（省 token） |
| `wda_info` | 一次返回：设备信息、电池、屏幕尺寸、当前 app + 屏幕文字 |
| `wda_screenshot` | 截图保存 PNG（兜底——先用 `wda_check`，看不清再截图） |
| `wda_source` | 完整 UI 元素树 XML（标签、类型、坐标） |
| `wda_find` | 按文字搜索元素，返回匹配的标签 + 点击坐标 |
| **操作** | |
| `wda_tap` | 点击坐标（x, y，单位 point） |
| `wda_tap_text` | 按文字找到元素并点击（页面加载中自动重试 3 次） |
| `wda_long_press` | 长按（弹出菜单、语音消息、删除等） |
| `wda_type` | 输入文字 |
| `wda_swipe` | 两点间滑动 |
| **导航** | |
| `wda_home` | 回主屏幕 |
| `wda_back` | 返回上一页（iOS 左边缘右滑手势） |
| `wda_scroll` | 滚动——方向：`down`、`up`、`left`、`right` |
| `wda_launch` | Spotlight 搜索打开任意 app |
| **工具** | |
| `wda_notifications` | 下拉通知栏 + 读取所有通知文字 |
| `wda_clipboard` | 读取剪贴板内容 |
| `wda_status` | 检查 WDA 是否运行 |
| `wda_start` | 启动/重启 WDA（自动 Tailscale 或本地 xcodebuild） |
| `wda_renew` | 续签 7 天证书 |

**设备兼容性：** 所有坐标在首次使用时自动校准。WDA-MCP 会自动检测屏幕尺寸和 Spotlight 布局——支持任何 iPhone 型号和 iOS 版本。

## 前置条件

- **macOS** + Xcode
- **iPhone**：首次设置需要 USB，之后可以用 Tailscale 远程
- **Python 3.12+** + `mcp[cli]`
- **Python 3.13**（远程启动需要，TCP tunnel 依赖 Python 3.13 的 SSL PSK 支持）
- **[pymobiledevice3](https://github.com/doronz88/pymobiledevice3)**：Python 3.12 和 3.13 都需要安装
- 免费 Apple 开发者账号（用于代码签名）

## 快速开始

### 1. 安装依赖

```bash
pip install "mcp[cli]"
brew install python@3.13
python3.12 -m pip install pymobiledevice3
python3.13 -m pip install --break-system-packages pymobiledevice3
```

### 2. 克隆并编译 WebDriverAgent

```bash
git clone https://github.com/appium/WebDriverAgent.git ~/Desktop/WebDriverAgent
cd ~/Desktop/WebDriverAgent
```

> ⚠️ **需要手动操作** — 免费 Apple ID 无法完全自动化这一步。需要在 Xcode 中手动配置签名。

在 Xcode 中打开 `WebDriverAgent.xcodeproj`：
- 选择 **WebDriverAgentRunner** target
- 在 **Signing & Capabilities** 中选择你的 Apple ID 团队
- 设置一个唯一的 **Bundle Identifier**（例如 `com.你的名字.WebDriverAgentRunner`）
- 编译：

```bash
xcodebuild build-for-testing \
    -project WebDriverAgent.xcodeproj \
    -scheme WebDriverAgentRunner \
    -destination "id=$(xcrun xctrace list devices | grep iPhone | head -1 | grep -oE '[A-F0-9-]{25,}')" \
    -allowProvisioningUpdates
```

### 3. 在 iPhone 上信任证书

进入 **设置 → 通用 → VPN与设备管理**，信任开发者证书。

### 4. 配置环境变量

```bash
cp config.example.env .env
# 编辑 .env，填入你的设备 UDID 和 Tailscale IP
```

查看设备 UDID：
```bash
xcrun xctrace list devices
```

### 5. 运行服务器

```bash
# stdio 模式（Claude Code / MCP 客户端）
python server.py

# HTTP 模式（端口 8200）
python server.py --http
```

### 6. 添加到 Claude Code

在 `.mcp.json` 中添加：
```json
{
  "mcpServers": {
    "wda": {
      "command": "python",
      "args": ["/path/to/wda-mcp/server.py"],
      "env": {
        "WDA_TAILSCALE_IP": "100.x.x.x",
        "WDA_DEVICE_ID": "你的设备UDID",
        "WDA_BUNDLE_ID": "com.你的名字.WebDriverAgentRunner.xctrunner"
      }
    }
  }
}
```

## 通过 Tailscale 远程访问

从任何地方控制你的 iPhone（不限局域网）：

1. 在 Mac 和 iPhone 上都安装 [Tailscale](https://tailscale.com)
2. 记下 iPhone 的 Tailscale IP（例如 `100.71.146.51`）
3. 在 `.env` 或 MCP 配置中设置 `WDA_TAILSCALE_IP`
4. WDA-MCP 会优先尝试 Tailscale IP，失败则回退到局域网发现

### 5G / 移动数据支持

WDA-MCP 可以在 iPhone 使用移动数据时启动和控制 WDA——**不需要 USB，不需要同一网络**。`wda_start()` 会自动：

1. 通过 Tailscale 检测 iPhone 的 RemotePairing 服务
2. 使用 `pymobiledevice3` 创建 TCP tunnel（需要 Python 3.13 + sudo）
3. 通过 tunnel 启动 WDA
4. 自动修补 pymobiledevice3 的一个 [DTX 时序问题](https://github.com/doronz88/pymobiledevice3/pull/1665)

**远程启动的要求：**
- iPhone 的 WiFi 开关必须打开（不需要连接任何网络——只要开关是开着的就行）
- 两台设备都运行 Tailscale
- Mac 需要 sudo 权限（创建 tunnel 需要 root 来建立 utun 网络接口）
- Python 3.13 + pymobiledevice3

**典型使用流程：**
1. 在家：iPhone 连着 WiFi → `wda_start()` 通过 Tailscale tunnel 启动 WDA
2. 出门：iPhone 离开 WiFi 范围（但 WiFi 开关还开着）→ WDA 继续运行
3. 在外面：通过 5G + Tailscale 从任何地方控制手机

> ### ⚠️ 出门前操作步骤（很重要，请仔细看！）
>
> **一句话原则：WiFi 按钮永远保持蓝色（打开状态），绝对不要关掉它。**
>
> 出门前的正确操作：
> 1. **连上 WiFi**，确认 WDA 启动成功（手机上出现 automation 界面）
> 2. **打开移动数据 / 5G**
> 3. **断开当前 WiFi 连接**——进入 设置 → WiFi → 点击当前网络 → "忽略此网络"
> 4. 确保**没有其他 WiFi 会自动连接**（把已保存的 WiFi 的"自动连接"关掉）
> 5. 出门！WDA 继续运行，走 5G + Tailscale
>
> **日常使用其实不需要这么麻烦**——出门时走远了 WiFi 自然会断，只要你不手动关 WiFi 按钮，提前开好 5G 就行。
>
> ---
>
> **为什么这样做？背后的原理：**
>
> iPhone 上"关 WiFi"有两种方式，效果完全不同：
>
> | 操作 | WiFi 按钮状态 | WDA 结果 |
> |------|-------------|---------|
> | 断开 WiFi 连接 / 走出范围 / 控制中心点一下 | 🔵 蓝色（开着） | ✅ WDA 继续运行 |
> | 设置里关掉 WiFi 开关 | ⚪ 灰色（关了） | ❌ WDA 约5秒后被杀 |
>
> iOS 把"WiFi 按钮关闭"当作信号，**强制清理所有开发者进程**（包括 WDA）。这是 iOS 系统级的限制，无法绕过。
>
> 但只要 WiFi 按钮是蓝色的——哪怕没连接任何网络——iOS 就不会动 WDA。

### 移动数据下 Tailscale 连不上？

如果 Tailscale 在 WiFi 下能用，但在移动数据下不行（连接超时或被拒绝），可能是你的运营商网络阻断了 Tailscale 使用的 WireGuard 协议。

**解决方案：搭建自定义 DERP 中继服务器。** DERP 是 Tailscale 内置的中继——当直连被阻断时，流量会走 DERP 中转。

1. 在一台移动网络能访问到的服务器上部署 DERP（VPS，或者有端口转发 / Cloudflare Tunnel 的 Mac）：
   ```bash
   go install tailscale.com/cmd/derper@latest
   derper --hostname=your-derp.example.com --verify-clients
   ```

2. 在 Tailscale [管理控制台](https://login.tailscale.com/admin/acls) 的 ACL 中添加：
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

3. 如果默认的 DERP 服务器也被阻断，可以在 derpMap 中设置 `"OmitDefaultRegions": true`。

设置完成后，移动数据流量通过你的 DERP 服务器中转，一切正常——远程启动 WDA、截图、控制，全部可用。不需要改代码。

## 在 claude.ai 中使用（聊天模式）

最有趣的用法是通过**聊天**——用自然语言跟 Claude 说话，让它控制你的手机。"帮我看看微信消息"、"截个图"、"打开第二页那个红色 app"——全在对话中完成。

需要 **HTTP 模式**，因为 claude.ai 需要通过网络访问你的 MCP 服务器。

### 方案 A：ngrok（最快，免费）

```bash
brew install ngrok
python server.py --http --port 8200 &
ngrok http 8200
```

ngrok 会给你一个公网 URL（如 `https://abc123.ngrok.io`），在 claude.ai 设置中添加为 MCP 服务器。

### 方案 B：Cloudflare Tunnel（稳定，免费，可用自定义域名）

```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared tunnel login
cloudflared tunnel create wda-mcp
python server.py --http --port 8200 &
cloudflared tunnel --url http://localhost:8200
```

### 添加到 claude.ai

1. 打开 claude.ai → 设置 → MCP 服务器
2. 用你的公网 URL（ngrok 或 Cloudflare）添加新服务器
3. 把所有 WDA 工具设为"始终允许"

## 自动续签

免费 Apple 开发者证书 7 天过期。设置自动续签：

```bash
crontab -e
0 3 */6 * * cd ~/Desktop/wda-mcp && bash scripts/renew_wda.sh >> /tmp/wda_renew.log 2>&1
```

## VPS 部署方案（不需要 Mac 一直开着）

把 wda-mcp 部署到 VPS 上，Mac 只在第一次编译 WDA 时用一次，之后就不需要了。

```
┌──────────┐         ┌──────────────────────────┐         ┌──────────┐
│  Claude  │──HTTP──→│         VPS              │←Tailscale→│  iPhone  │
│ (任何地方) │         │  wda-mcp (MCP server)    │          │  WDA     │
└──────────┘         │  pymobiledevice3         │          │  Tailscale│
                     │  Tailscale (exit node)   │          └──────────┘
                     └──────────────────────────┘
```

**VPS 同时承担三个角色：**
1. **MCP 服务器** — Claude 连这里操控手机
2. **Tailscale 节点** — 通过 Tailscale 连到 iPhone
3. **Exit node**（可选）— 中国用户可以用它替代 Shadowrocket 翻墙，解决 VPN 冲突

### VPS 上的安装步骤

```bash
# 1. 安装 Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --advertise-exit-node  # 开启 exit node（可选）

# 2. 安装 Python 3.13
# Ubuntu/Debian:
sudo apt install python3.13 python3.13-venv
# 或用 pyenv: pyenv install 3.13

# 3. 安装 wda-mcp
git clone https://github.com/Qizhan7/wda-mcp.git
cd wda-mcp
pip install "mcp[cli]"
pip install pymobiledevice3

# 4. 打 DTX patch
sudo python3 scripts/patch_pymobiledevice3.py

# 5. 启动 MCP 服务器（HTTP 模式，对外提供服务）
WDA_TAILSCALE_IP=<iPhone的Tailscale IP> \
WDA_DEVICE_ID=<设备UDID> \
WDA_BUNDLE_ID=<WDA Bundle ID> \
python server.py --http
```

### iPhone 端设置

1. 安装 Tailscale，加入和 VPS 同一个 Tailscale 网络
2. （可选）在 Tailscale app 里选择 VPS 作为 exit node → 替代 Shadowrocket 翻墙
3. 保持 WiFi 按钮蓝色（开着）

### WDA 首次编译（唯一需要 Mac 的地方）

在 Mac 上用 Xcode 编译并安装 WDA 到 iPhone（只需要做一次）。之后 VPS 可以远程启动/控制 WDA，Mac 不用再开。

每 7 天需要续签证书：可以在 Mac 上手动跑 `wda_renew`，或者用 GitHub Actions 自动续签（见下面 "没有 Mac" 部分）。

## 架构

```
┌──────────────────┐     MCP (stdio/HTTP)     ┌──────────────────┐
│   AI 代理         │◄────────────────────────►│   wda-mcp        │
│ (Claude Code)    │                          │   server.py      │
└──────────────────┘                          └────────┬─────────┘
                                                       │ HTTP :8100
                                              ┌────────▼─────────┐
                                              │  WebDriverAgent  │
                                              │  (iPhone 上)      │
                                              └────────┬─────────┘
                                                       │
                                              ┌────────▼─────────┐
                                              │  iPhone 屏幕      │
                                              │  点击/滑动/输入    │
                                              └──────────────────┘

         网络选项：
         ├─ USB（仅本地）
         ├─ WiFi 局域网（同一网络）
         └─ Tailscale VPN（任何地方——WiFi、5G、任何网络）
```

## ⚠️ 容易踩的坑

### 网络环境的坑

> **WiFi 直连不通（No route to host）？先检查这两个：**
>
> **1. Mac 和 iPhone 是否在同一网段？**
> 很多路由器的 2.4G 和 5G WiFi 是不同的 SSID，可能在不同子网。确保 Mac 和 iPhone **连的是同一个 WiFi 名称**。或者在路由器设置里勾选"双频合一"/"启用双频设定为相同的SSID"。
>
> **2. 路由器有没有开 AP 隔离？**
> 有些路由器默认开启 AP 隔离（客户端隔离/终端限制），阻止同一 WiFi 上的设备互相通信。国内路由器（华为/小米/运营商定制）更常见。
>
> 检查方法：
> ```bash
> ping <iPhone的WiFi IP>  # 不通 → 网段不同或 AP 隔离
> ```
>
> 解决方案：
> - 确认两个设备连同一个 SSID（同频段）
> - 登录路由器后台 → 关闭"AP隔离"/"客户端隔离"/"启用终端限制"
> - **绕过**：用 Tailscale IP（100.x.x.x）代替 WiFi IP

> **iPhone 的 Tailscale 经常掉线 / 显示 offline？**
>
> 去 iPhone **设置 → 通用 → VPN与设备管理 → VPN → Tailscale → 开启"按需连接"（Connect On Demand）**。
>
> 不开这个的话，iOS 会在后台杀掉 Tailscale，导致 Tailscale 掉线。开了之后会自动重连。

### WiFi 无线调试的坑

> **用 xcodebuild 启动的 WDA 不能通过 tunnel 访问！**
>
> 这是最常见的误区。xcodebuild 启动的 WDA 监听在手机的 WiFi IP 上（如 192.168.1.14:8100），但这个端口**不在 pymobiledevice3 tunnel 的路由里**。
>
> **正确做法：用 pymobiledevice3 的 xcuitest 启动 WDA**，这样 WDA 的端口会通过 tunnel 暴露出来：
> ```bash
> # ✅ 正确 — WDA 通过 tunnel 可访问
> python3.12 -m pymobiledevice3 developer dvt xcuitest --rsd <tunnel地址> <端口> <BundleID>
>
> # ❌ 错误 — WDA 端口不在 tunnel 路由里
> xcodebuild test -destination "id=<UDID>" ...
> ```

> **xcuitest 连上就断（DTX 20 秒超时）？**
>
> 这是 pymobiledevice3 的一个 bug——通过 WiFi/远程 tunnel 启动 xcuitest 时，设备发送的 DTX 消息在服务注册之前到达，导致连接中断。
>
> **必须打 patch！** 运行项目里的 patch 脚本：
> ```bash
> sudo python3.12 scripts/patch_pymobiledevice3.py
> sudo python3.13 scripts/patch_pymobiledevice3.py
> ```
> 这会自动修复。详情见 [PR #1665](https://github.com/doronz88/pymobiledevice3/pull/1665)。

> **Python 3.12 建不了 WiFi tunnel？**
>
> iOS 18.2+ 移除了 QUIC 协议支持，TCP tunnel 需要 Python 3.13 的 SSL PSK 功能。
> ```bash
> # ❌ Python 3.12 — SSL PSK 不支持，tunnel 建不了
> sudo python3.12 -m pymobiledevice3 remote start-tunnel -t wifi
>
> # ✅ Python 3.13 — 可以
> sudo python3.13 -m pymobiledevice3 remote start-tunnel -t wifi
> ```
> **tunnel 用 Python 3.13 建，xcuitest 用 Python 3.12 跑**——两个版本各管一件事。

> **devicectl 显示 "connecting" 连不上？**
>
> 重启 Mac 的 remoted 服务：
> ```bash
> sudo pkill -9 remoted
> # 等 5 秒，设备会变成 "available (paired)"
> ```

### 5G / 移动数据的坑

> **关了 WiFi 开关 WDA 就死了？**
>
> 这是 iOS 的系统限制。**关 WiFi 开关**和**断开 WiFi 连接**是两回事：
> - 设置里关掉 WiFi 开关（变灰）→ iOS 杀 WDA 进程，约 5 秒死亡
> - 断开 WiFi 连接 / 走出范围 / 控制中心点一下 WiFi → WDA 不受影响
>
> **只要 WiFi 开关保持打开（绿色），WDA 就不会被杀。** 大多数人日常不会关 WiFi 开关。

> **5G 下 Tailscale 连不上？**
>
> 运营商可能阻断了 WireGuard 协议。搭建自定义 DERP 中继服务器解决（详见上面的 DERP 部分）。

> **5G 下不能启动 WDA，只能在 WiFi 下启动？**
>
> 对。iOS 只在 WiFi 连接时开启 RemotePairing 服务（端口 49152）。启动 WDA 需要这个服务。
> 但启动后出门（WiFi 断开、开关不关），WDA 继续跑。
>
> **典型流程：在家 WiFi 启动 → 出门 5G 继续用。**

## 常见问题

**Q：需要付费 Apple 开发者账号吗？**
A：不需要。免费账号就行，但每 7 天需要重新签名（用 `wda_renew` 或 cron 脚本）。

**Q：支持哪些 iPhone？**
A：支持 WebDriverAgent 的所有 iPhone——一般是 iPhone 6s 及以后的机型。

**Q：截图坐标对不上？**
A：WDA 用的是 **points**，不是像素。iPhone 14 Pro 是 393×852 points。用 `wda_source` 获取精确坐标。

**Q：WDA 一直断开？**
A：确保 iPhone 不会自动锁屏。设置 → 显示与亮度 → 自动锁定 → 永不。

**Q：可以不用 Tailscale 吗？**
A：可以。WDA-MCP 会回退到局域网 IP 发现。Tailscale 只是增加了远程访问能力。

## 致谢

- [WebDriverAgent](https://github.com/appium/WebDriverAgent) — Facebook/Appium 的 iOS 自动化框架
- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) — iOS 设备通信的 Python 库
- [Tailscale](https://tailscale.com) — 零配置 mesh VPN
- [Model Context Protocol](https://modelcontextprotocol.io) — Anthropic 的 AI 工具调用开放协议
