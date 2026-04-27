[English README](README.md)

# WDA MCP — 用 AI 远程控制 iPhone

一个独立的 [MCP](https://modelcontextprotocol.io) 服务器，让 AI 通过网络控制你的 iPhone。基于 Apple 的 [WebDriverAgent](https://github.com/appium/WebDriverAgent)，配合 [Tailscale](https://tailscale.com) 实现从任何地方远程控制——不限于局域网。

点击按钮、滑动屏幕、截图、输入文字、查看 UI 元素——全部通过自然语言完成。

## 先选接入路线

WDA-MCP 需要支持**读+写**的 MCP：能看屏幕，也能点击、输入、滑动。只读 MCP = 能看不能点。

| 你想用 | 推荐入口 | 说明 |
|------|------|------|
| **Claude Code / Claude Desktop** | `server.py` stdio | 本地 MCP，最稳。 |
| **claude.ai 网页聊天** | `server.py --http` + HTTPS tunnel | 免费版可用 1 个自定义 MCP 连接器，适合自然语言控手机。 |
| **Codex** | `server.py` stdio | 需要把 `wda` 加进 Codex 的 MCP 配置。 |
| **ChatGPT 网页版 / 手机浏览器网页版** | `server_chatgpt.py` + HTTPS `/mcp` | 走 ChatGPT Developer Mode，详见 [`CHATGPT_CN.md`](CHATGPT_CN.md)。 |
| **ChatGPT iOS/Android 原生 App** | 暂不推荐 | 自定义 MCP App 目前主要按网页版路线测试，原生 App 不要当作稳定入口。 |

> Claude 已经跑通的用户不用改配置。ChatGPT 单独走 `server_chatgpt.py`，不要和 Claude 的原路线混在一起。

## 平台兼容性

### Anthropic（Claude）

| 产品 | 自定义 MCP？ | 能操控？ | 最低计划 | 备注 |
|------|:----------:|:------:|---------|------|
| **claude.ai**（网页） | ✅ | ✅ | 免费（1 个连接器） | 最省钱的聊天入口。 |
| **Claude Desktop** | ✅ | ✅ | 免费 | 适合桌面常驻。 |
| **Claude Code**（命令行） | ✅ | ✅ | Pro 或 API | 适合开发和调试。 |

### OpenAI（ChatGPT / Codex）

| 产品 | 自定义 MCP？ | 能操控？ | 推荐入口 |
|------|:----------:|:------:|---------|
| **ChatGPT 网页版** | ✅ Developer Mode | ⚠️ 看账号/工作区权限 | `server_chatgpt.py` + HTTPS `/mcp` |
| **手机浏览器打开 ChatGPT 网页版** | ✅ 可尝试 | ⚠️ 看网页端是否开放入口 | 同上 |
| **ChatGPT 原生手机 App** | ⚠️ 不稳定/不建议 | ⚠️ 不保证 | 暂时用浏览器网页版 |
| **Codex CLI / Codex App** | ✅ | ✅ | `server.py` stdio |

ChatGPT Developer Mode / MCP Apps 仍在 beta。写操作通常会弹确认框，完整读写能力会受账号、计划和工作区开关影响。OpenAI 内置连接器（如 Drive、Notion）和自定义 MCP 不是一回事；这里说的是你自己暴露的 WDA-MCP。

### 其他 MCP 客户端

| 产品 | 自定义 MCP？ | 能操控？ | 备注 |
|------|:----------:|:------:|------|
| **Gemini CLI** | ✅ | ✅ | 网页版 Gemini 不支持自定义 MCP。 |
| **Mistral Le Chat** | ✅ | ✅ | 可作为免费聊天入口测试。 |
| **Cursor / Windsurf / Cline** | ✅ | ✅ | 适合开发环境内使用。 |

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

Claude / Codex 继续使用原来的 `server.py`：

```bash
# stdio 模式（Claude Code / MCP 客户端）
python server.py

# HTTP 模式（端口 8200）
python server.py --http
```

ChatGPT 不走这个入口，使用 [`CHATGPT_CN.md`](CHATGPT_CN.md) 里的 `server_chatgpt.py`。

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

### 7. 添加到 Codex

Codex 使用 `~/.codex/config.toml`。如果你的 `python` 不是 3.12，请把 `command` 改成 `/opt/homebrew/bin/python3.12`。

```toml
[mcp_servers.wda]
command = "python3.12"
args = ["/path/to/wda-mcp/server.py"]
cwd = "/path/to/wda-mcp"
startup_timeout_sec = 20
tool_timeout_sec = 300
```

重启 Codex 后，用 `/mcp` 或 `codex mcp list` 确认 `wda` 出现。

## 阶段 1：USB 本地验证（先证明 WDA 能跑）

**目标：** 只验证 WDA 本体：签名、证书、UDID、Bundle ID、Xcode 构建、WDA 能不能启动。这里先不要排 AP 隔离、Tailscale、5G。

**过关标准：** iPhone 顶部出现 automation 界面；如果 Mac 和 iPhone 此时也在同一个 WiFi，`wda_status` 和 `wda_screenshot` 也能正常返回。

1. iPhone 用 USB 接 Mac，保持解锁；手机可以先连着家里 WiFi，但这一步不要拔 USB。
2. 确认 iPhone 已经信任电脑，并在 **设置 → 通用 → VPN与设备管理** 里信任开发者证书。
3. `.env` 里先填好 `WDA_DEVICE_ID`、`WDA_BUNDLE_ID`、`WDA_PROJECT_DIR`；`WDA_TAILSCALE_IP` 可以先不填。
4. 启动 MCP 后调用 `wda_start()`，或者在 Xcode 里直接运行 `WebDriverAgentRunner`。
5. iPhone 顶部出现 automation 界面后，WDA 本体就算过第一关；如果 Mac 和 iPhone 此时也在同一个 WiFi，可以顺手测试 `wda_status` 和 `wda_screenshot`。

**卡住先查：**
- iPhone 是否已经信任电脑和开发者证书。
- `WDA_DEVICE_ID`、`WDA_BUNDLE_ID`、`WDA_PROJECT_DIR` 是否填对。
- Xcode 里 WDA 是否能 build 成功，Bundle ID 是否和签名配置一致。
- 手机是否解锁、是否自动锁屏、`remoted` 是否卡住。

如果 USB 阶段都不通，不要继续排 WiFi/5G。

## 阶段 2：USB → WiFi 切换检查清单

**目标：** 从“USB 能启动 WDA”推进到“拔掉 USB 后，Mac 还能通过同一个 WiFi 找到 iPhone”。很多人第一次卡在这一步，所以先只排局域网和 Xcode 无线配对。

**过关标准：** Xcode 里已经勾选 **Connect via network**；拔掉 USB 后，Mac 能 `ping <iPhone WiFi IP>`，并且 `curl http://<iPhone WiFi IP>:8100/status` 能返回 WDA 状态。

先分清三件事：

| 目标 | 你在验证什么 | 常见失败原因 |
|------|-------------|-------------|
| **局域网直连** | Mac 能访问 `http://<iPhone WiFi IP>:8100/status` | 不同子网、访客 WiFi、AP/客户端隔离、多网卡/双路由走错出口、Mac/iPhone VPN 抢路由 |
| **Tailscale 访问** | Mac 能访问 `http://<iPhone Tailscale IP>:8100/status` | iPhone Tailscale 掉线、另一个 VPN 抢占、移动网络或路由策略限制 UDP |
| **无线启动 WDA** | Mac 能连 iPhone 的 RemotePairing 端口 `49152` | 没做 Xcode 网络配对、Tailscale/网络切换中断、手机锁屏、`remoted` 卡住 |

**不要一拔 USB 就直接出门。** 先在家里按这个顺序验证：

1. USB 连着 iPhone，确认 WDA 已经在手机上跑起来。
2. Mac 和 iPhone 连同一个普通 WiFi/同一个路由器。不要用访客网络、校园网、酒店网、公司隔离网。如果 Mac 同时插网线又连 WiFi，先临时断开不相关的那条网络。
3. 在 Xcode 里打开 Window → Devices and Simulators → 选中 iPhone → 勾选 **Connect via network**。Apple 的[无线设备配对文档](https://help.apple.com/xcode/mac/current/en.lproj/devbc48d1bad.html)也是先 USB 配对，再断开线缆。
4. 查 iPhone 的 WiFi IP：设置 → WiFi → 当前网络右侧 `i`。
5. 在 Mac 上测局域网直连：
   ```bash
   ping <iPhone的WiFi IP>
   route -n get <iPhone的WiFi IP> | grep -E 'interface|gateway|source'
   curl -m 3 http://<iPhone的WiFi IP>:8100/status
   ```
6. 如果要走 Tailscale，再测：
   ```bash
   tailscale status
   tailscale ping <iPhone的Tailscale IP>
   curl -m 3 http://<iPhone的Tailscale IP>:8100/status
   ```
7. 如果要无线启动/重启 WDA，再测 RemotePairing：
   ```bash
   python3.12 - <<'PY'
   import socket
   ip = "<iPhone的Tailscale IP 或 WiFi IP>"
   s = socket.socket()
   s.settimeout(3)
   s.connect((ip, 49152))
   print("RemotePairing OK")
   PY
   ```

Apple 的[无线设备排障文档](https://help.apple.com/xcode/mac/current/en.lproj/devac3261a70.html)也建议先确认设备已配对、Mac 和设备在同一网络，并用 `ping <设备 IP>` 检查连通性。

**卡住先查：**
- Mac 和 iPhone 是否连同一个普通 WiFi/同一个路由器，不要用访客网络、校园网、酒店网、公司隔离网。
- `ping <iPhone WiFi IP>` 不通时，优先怀疑不同子网、AP/客户端隔离、Mac 多网卡走错路由。
- Mac 同时插网线又连 WiFi 时，先临时拔掉不相关的网络，再测。
- Xcode 里是否真的完成 **Connect via network**；不确定就重新 USB 配对一次。
- 能 `curl :8100` 只代表能访问已运行的 WDA；能不能无线启动/重启还要看 `49152`。

## 阶段 3：WiFi / 局域网使用（先跑通这一步）

**目标：** 让 Claude/Codex/MCP 在同一个 WiFi/路由器下稳定控制 iPhone。5G 和 VPS 都建立在这一步之上。

**过关标准：** `curl http://<iPhone WiFi IP>:8100/status` 能稳定返回 WDA 状态，`wda_status`、`wda_screenshot` 能正常使用。

1. iPhone 连 WiFi，Mac 连同一个 WiFi/路由器。
2. 用 USB 或 Xcode 启动 WDA，等手机上出现 automation 界面。
3. 在 iPhone 设置 → WiFi → 当前网络右侧 `i` 里找到 WiFi IP。
4. 在 Mac 上确认 WDA 可访问：
   ```bash
   ping <iPhone的WiFi IP>
   curl -m 3 http://<iPhone的WiFi IP>:8100/status
   ```
5. `curl` 能看到 WDA 状态后，Claude/Codex/MCP 就可以通过这个 WiFi IP 控制手机。

**卡住先查：**
- 是否同一子网、同一个普通 SSID，不要用访客 WiFi。
- 路由器是否开启 AP 隔离/客户端隔离/禁止终端互访。
- Mac 是否同时连了网线和另一个 WiFi，导致访问 iPhone WiFi IP 时走错出口。
- 全局代理是否抢了局域网路由；局域网网段要走 DIRECT。

如果这一步不通，不要继续排 5G。

## 阶段 4：通过 Tailscale 远程访问

**目标：** 从任何地方控制你的 iPhone（不限局域网）。

**过关标准：** `tailscale status` 里 iPhone 在线，`tailscale ping <iPhone Tailscale IP>` 成功，`curl http://<iPhone Tailscale IP>:8100/status` 能返回 WDA 状态。

1. 在 Mac 和 iPhone 上都安装 [Tailscale](https://tailscale.com)
2. 记下 iPhone 的 Tailscale IP（在 `100.64.0.0/10` 这段 CGNAT 范围里，长得像 `100.x.x.x`）
3. 在 `.env` 或 MCP 配置中设置 `WDA_TAILSCALE_IP`
4. WDA-MCP 会优先尝试 Tailscale IP；失败时会读取 `/tmp/wda_run.log` 里的 WDA URL，并试几个常见局域网 IP。新手最稳还是显式设置 `WDA_TAILSCALE_IP`

**卡住先查：**
- iPhone 上 Tailscale 是否在线；不稳定时打开 **VPN On Demand / 按需连接**。
- iPhone 上是否同时开了其他 VPN/代理 App；测试时先只开 Tailscale。
- Mac 的代理/VPN 是否把 `100.64.0.0/10` 这段 Tailscale 地址抢走。
- `WDA_TAILSCALE_IP` 是否填的是 iPhone 的 Tailscale IP，不是 Mac/VPS 的 IP。
- 如果 Tailscale 能 ping 但 `8100` 不通，说明 WDA 可能没启动或已经掉了，先回到 WiFi 阶段启动。

## 阶段 5：5G / 移动数据支持（最后再测）

**目标：** iPhone 离开 WiFi 后，继续通过 5G + Tailscale 控制已运行的 WDA；如果 `49152` 可达，再尝试远程启动/重启。

**过关标准：** 切到 5G 后，`tailscale ping <iPhone Tailscale IP>` 和 `curl http://<iPhone Tailscale IP>:8100/status` 仍然可用。`49152` 可达是加分项，代表可以尝试远程启动/重启。

WDA-MCP 可以在 iPhone 使用移动数据时控制 WDA——**不需要 USB，不需要同一局域网**。启动/重启 WDA 依赖 iPhone 的 RemotePairing 服务；判断标准不是“现在是 WiFi 还是 5G”，而是 Tailscale IP 上的 `49152` 是否可达。`wda_start()` 在 RemotePairing 端口 `49152` 可达时会自动：

5G 远程启动可能因为移动网络策略、Tailscale 重连、DERP/UDP 受限、VPN/代理冲突、WiFi → 5G 切换抖动等原因失败。如果尝试后 `49152` 不通或 WDA 启动不稳，就回到上面的 WiFi 局域网流程先启动 WDA，再按下面的重要流程切到 5G 继续控制。

1. 通过 Tailscale 检测 iPhone 的 RemotePairing 服务
2. 使用 `pymobiledevice3` 创建 TCP tunnel（需要 Python 3.13 + sudo）
3. 通过 tunnel 启动 WDA
4. 检查 pymobiledevice3 是否包含 [DTX 时序修复](https://github.com/doronz88/pymobiledevice3/pull/1665)，旧版缺失时自动补上

**远程启动/重启的要求：**
- iPhone 已经在 Xcode 里完成 **Connect via network** 配对
- Tailscale IP 上的 RemotePairing 端口 `49152` 可达
- iPhone 的 WiFi 开关必须保持打开；不一定要连接任何 WiFi，但绝对不要把 WiFi 总开关关掉
- 如果 5G 切换后 `49152` 不可达，先回到 WiFi 下启动，再离开 WiFi 继续控制
- 两台设备都运行 Tailscale
- Mac 需要 sudo 权限（创建 tunnel 需要 root 来建立 utun 网络接口）
- Python 3.13 + pymobiledevice3

**典型使用流程：**
1. 在家：iPhone 连着 WiFi → `wda_start()` 通过 Tailscale tunnel 启动 WDA
2. 出门：iPhone 离开 WiFi 范围（但 WiFi 开关还开着）→ WDA 继续运行
3. 在外面：通过 5G + Tailscale 从任何地方控制手机；如果 `49152` 仍然可达，也可以远程重启 WDA

**卡住先查：**
- WiFi 按钮是不是仍然打开。不要在设置里关掉 WiFi 总开关。
- `8100` 掉了：优先查 Tailscale/移动网络/DERP/VPN 冲突。
- `8100` 还在但 `49152` 掉了：已运行的 WDA 还能控制，但暂时不能远程重启；回 WiFi 下启动最稳。
- 切换瞬间掉线：用下面的监控脚本看是 `ping`、`8100`、还是 `49152` 先掉。
- 尝试 5G 不稳时，不要硬排到崩溃，先用 WiFi 启动保活方案。

> ### ⚠️ 重要流程：出门前操作步骤（很重要，请仔细看！）
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
> 这个流程是实测能保住 5G 下 WDA 不断的关键，不要跳步骤。
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

如果 Tailscale 在 WiFi 下能用，但在移动数据下不行（连接超时或被拒绝），可能是移动网络策略限制了 Tailscale 使用的 WireGuard 协议。

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

## 统一高级排查：端口、脚本、网络环境

这一节是跨阶段排查。新人先按上面 5 个阶段走；只有卡住时，再看这里对应项。

### 先认两个端口

- `8100`：WDA HTTP 服务。通了就说明可以访问已运行的 WDA，可以截图、点按、读 UI。
- `49152`：iPhone RemotePairing 服务。通了才有机会无线启动/重启 WDA。
- **能访问 WDA 不等于能启动 WDA。** 5G 下如果 `8100` 通但 `49152` 不通，通常还能继续控制已运行的 WDA，只是暂时不能远程重启。

### 一键诊断 USB/WiFi/Tailscale

```bash
bash scripts/diagnose_usb_wifi.sh <iPhone的WiFi IP> <iPhone的Tailscale IP>
```

帮别人排查时，让她把诊断脚本的完整输出贴回来，尤其是这几段：`Mac local IPs`、`Mac network snapshot`、`Mac route to iPhone WiFi IP`、`LAN ping`、`WiFi WDA status`、`Tailscale ping`。同时问清楚 Mac 是不是同时连了网线和 WiFi、iPhone 连的是哪个路由器/SSID。

如果问题发生在“WiFi 切到 5G”的瞬间，在 Mac 或 VPS 上开一个监控：

```bash
bash scripts/watch_handoff.sh <iPhone的Tailscale IP>
```

看哪一列先掉：`ping` 掉是 Tailscale/网络切换；`8100` 掉是 WDA 访问断；只有 `49152` 掉说明还能控制已运行的 WDA，但暂时不能重启。

### 复杂网络环境额外注意

- **AP 隔离/客户端隔离很常见。** 现象是 Mac 和 iPhone 都能上网，但 `ping <iPhone WiFi IP>` 不通。路由器后台可能叫“AP隔离”“客户端隔离”“访客网络隔离”“禁止终端互访”。关掉它，或者换家庭/旅行路由器的普通 SSID。
- **不要用访客 WiFi。** 很多访客网络默认禁止设备互相访问，WDA 的 `8100` 端口会被挡住。
- **2.4G/5G 或两个路由器可能不在同一子网。** 看 iPhone IP 和 Mac IP 是否像 `192.168.1.x` / `192.168.1.y` 这样同网段；如果一个是 `192.168.1.x`，另一个是 `192.168.31.x`，基本就是跨路由/跨子网了。
- **Mac 同时连网线和 WiFi 时可能走错出口。** 例如 Mac 网线连路由器 A、WiFi 连路由器 B，而 iPhone 在 B 上。用 `route -n get <iPhone WiFi IP>` 看 `interface` 和 `source address`；如果不是通向 iPhone 所在网络，先拔网线/关闭另一个 WiFi/调整网络服务顺序再测。
- **其他 VPN/代理 App 可能和 Tailscale 冲突。** Tailscale 官方也说明 iOS 上通常只能同时有一个活跃 VPN，另一个 VPN 还可能丢弃 Tailscale 流量。测试时先只开 Tailscale；如果必须同时使用代理，优先用 Tailscale exit node，减少多个 VPN 抢路由。参考：[Tailscale + other VPNs](https://tailscale.com/docs/reference/faq/other-vpns)。
- **Mac 上的全局代理也可能抢路由。** 如果使用全局代理模式，要绕过局域网和 Tailscale 网段，至少把 `192.168.0.0/16`、`10.0.0.0/8`、`172.16.0.0/12`、`100.64.0.0/10` 设为 DIRECT。

### pymobiledevice3 / tunnel 常见坑

> **用 xcodebuild 启动的 WDA 不能通过 tunnel 访问！**
>
> `xcodebuild` 启动的 WDA 监听在手机的 WiFi IP 上（如 `192.168.1.14:8100`），但这个端口不在 pymobiledevice3 tunnel 的路由里。要通过 tunnel 访问，使用：
> ```bash
> python3.12 -m pymobiledevice3 developer dvt xcuitest --rsd <tunnel地址> <端口> <BundleID>
> ```

> **xcuitest 连上就断（DTX 20 秒超时）？**
>
> [PR #1665](https://github.com/doronz88/pymobiledevice3/pull/1665) 已经合并到 pymobiledevice3 master。普通 `pip install pymobiledevice3` 如果还停在旧 release，就运行项目里的兼容 patch：
> ```bash
> sudo python3.12 scripts/patch_pymobiledevice3.py
> ```
> 如果你安装的是已经包含 PR #1665 的版本，这个脚本会直接显示已包含修复/已 patch，不需要重复处理。

> **Python 3.12 建不了 WiFi tunnel？**
>
> iOS 18.2+ 移除了 QUIC 协议支持，TCP tunnel 需要 Python 3.13 的 SSL PSK 功能。**tunnel 用 Python 3.13 建，xcuitest 用 Python 3.12 跑**，两个版本各管一件事。

> **devicectl 显示 "connecting" 连不上？**
>
> 重启 Mac 的 remoted 服务：
> ```bash
> sudo pkill -9 remoted
> # 等 5 秒，设备会变成 "available (paired)"
> ```

## ⚠️ 安全：HTTP 模式的鉴权

本地 stdio 模式（Claude Code / Codex）不开端口，本身是安全的。**有风险的是 HTTP 模式**（`server.py --http` / `server_chatgpt.py`）——HTTP 模式暴露的都是真实写操作：点击、输入、截屏、读剪贴板、打开任意 app。**不要把 HTTP 模式裸奔暴露到公网。**

现在 server 自带 **OAuth 2.0 + Bearer** 鉴权。**HTTP 模式没有 access token 就拒绝启动。**

### 一次性配置

```bash
python scripts/generate_oauth_creds.py
```

会写一份 `~/.wda-oauth.json`（chmod 600），里面有随机生成的 `client_id`、`client_secret`、`access_token`。`access_token` 是 MCP 客户端要带的 Bearer 头，按密码保管。

### 启动 HTTP 模式

```bash
bash scripts/start_http.sh
```

或前台运行（调试时方便）：

```bash
python server.py --http
```

启动器会读 `~/.wda-oauth.json`（或 `WDA_OAUTH_*` 环境变量），在 `0.0.0.0:8200` 起 uvicorn，并暴露：

- `/mcp` — MCP 端点。非回环来源必须带 `Authorization: Bearer <access_token>`。
- `/.well-known/oauth-protected-resource`、`/.well-known/oauth-authorization-server` — OAuth 自动发现。
- `/oauth/authorize`、`/oauth/token` — 完整 OAuth 2.0 流程（`authorization_code` 和 `client_credentials`），给走标准 OAuth 接入的 MCP 客户端用。

回环（`127.0.0.1`、`::1`）来源不查 token——本机其他进程可以直接连 `http://localhost:8200/mcp`，方便本地脚本调用。

### MCP 客户端怎么填 token

| 客户端 | 接入方式 |
|------|---------|
| **claude.ai 自定义连接器** | 加一个 custom header：`Authorization: Bearer <access_token>` |
| **ChatGPT Developer Mode** | 直接填 token，或让它走标准 OAuth `authorization_code` 流程 |
| **curl / 脚本** | `curl -H "Authorization: Bearer $TOKEN" https://your-url/mcp` |
| **本地 Claude Code（stdio）** | 不需要 token，stdio 不走 HTTP |

### 进一步加固（建议长期固定 URL 都做）

域名长期在线的话，再叠一层 Cloudflare Access：

1. Cloudflare Zero Trust → Access → Applications → Add self-hosted application
2. Application domain = 你的 tunnel 域名（如 `wda-mcp.example.com`）
3. 加 policy，比如 `Include → Emails → 你的邮箱`，或 Google / GitHub 登录

万一 token 泄露，外部还要先过 Cloudflare Access 这关。ChatGPT / claude.ai 的 connector 可以用 Cloudflare Access 的 **Service Token**（header 形式）做非交互鉴权。

### 永远不要

- 把 ngrok / `*.trycloudflare.com` 这种随机 URL 当长期方案，临时测完关掉 tunnel。
- 把 `~/.wda-oauth.json` 或 access token 贴到截图、聊天、issue、git 里。
- 怀疑泄露：`python scripts/generate_oauth_creds.py --force` 重新生成，重启 server。
- 为了"让某个客户端连上"就把启动器的 token 检查改弱——去修客户端，不要削弱 server。

## 在 claude.ai 中使用（聊天模式）

> ⚠️ 暴露到公网前，先完成上面的[安全配置](#️-安全http-模式的鉴权)（`generate_oauth_creds.py` + `start_http.sh`）。下面这段是怎么把 8200 暴露出去；server 这边强制 Bearer 鉴权。

最有趣的用法是通过**聊天**——用自然语言跟 Claude 说话，让它控制你的手机。"帮我看看微信消息"、"截个图"、"打开第二页那个红色 app"——全在对话中完成。

需要 **HTTP 模式**，因为 claude.ai 需要通过网络访问你的 MCP 服务器。

### 方案 A：ngrok（最快，免费）

```bash
brew install ngrok
python server.py --http &
ngrok http 8200
```

ngrok 会给你一个公网 URL（如 `https://abc123.ngrok.io`），在 claude.ai 设置中添加为 MCP 服务器。

### 方案 B：Cloudflare Tunnel（稳定，免费，可用自定义域名）

```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared tunnel login
cloudflared tunnel create wda-mcp
python server.py --http &
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
3. **Exit node**（可选）— 可以替代额外的 VPN/代理路径，减少 VPN 冲突

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

# 4. 检查/补上 DTX 兼容修复（已包含 PR #1665 的版本会直接跳过）
sudo python3 scripts/patch_pymobiledevice3.py

# 5. 启动 MCP 服务器（HTTP 模式，对外提供服务）
WDA_TAILSCALE_IP=<iPhone的Tailscale IP> \
WDA_DEVICE_ID=<设备UDID> \
WDA_BUNDLE_ID=<WDA Bundle ID> \
python server.py --http
```

### iPhone 端设置

1. 安装 Tailscale，加入和 VPS 同一个 Tailscale 网络
2. （可选）在 Tailscale app 里选择 VPS 作为 exit node → 减少额外 VPN/代理冲突
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
A：可以，但 Mac 必须能访问 iPhone 的 WiFi IP。必要时从 `/tmp/wda_run.log` 找 `ServerURLHere`；自动猜 IP 只是兜底。Tailscale 只是增加远程访问能力。

## 致谢

- [WebDriverAgent](https://github.com/appium/WebDriverAgent) — Facebook/Appium 的 iOS 自动化框架
- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) — iOS 设备通信的 Python 库
- [Tailscale](https://tailscale.com) — 零配置 mesh VPN
- [Model Context Protocol](https://modelcontextprotocol.io) — Anthropic 的 AI 工具调用开放协议
