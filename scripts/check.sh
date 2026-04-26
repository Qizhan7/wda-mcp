#!/bin/bash
# WDA 5G Upgrade — 环境检查
# 用法：bash check.sh [TAILSCALE_IP]

echo "=== WDA 5G 升级环境检查 ==="
echo ""

OK=0; FAIL=0

check() {
  if eval "$2" > /dev/null 2>&1; then
    echo "  ✅ $1"
    OK=$((OK+1))
  else
    echo "  ❌ $1 — $3"
    FAIL=$((FAIL+1))
  fi
}

# Python
check "Python 3.12" "python3.12 --version" "brew install python@3.12"
check "Python 3.13" "python3.13 --version" "brew install python@3.13"

# pymobiledevice3
check "pymobiledevice3 (3.12)" "python3.12 -m pymobiledevice3 version" "python3.12 -m pip install pymobiledevice3"
check "pymobiledevice3 (3.13)" "python3.13 -m pymobiledevice3 version" "python3.13 -m pip install --break-system-packages pymobiledevice3"

# DTX patch
check "DTX patch 已安装" "python3.12 -c \"
import importlib, site, pathlib
for b in site.getsitepackages()+[site.getusersitepackages()]:
    t = pathlib.Path(b)/'pymobiledevice3/services/dvt/testmanaged/xcuitest.py'
    if t.exists() and 'REGISTER_SERVICES' in t.read_text(): exit(0)
exit(1)
\"" "运行: sudo python3.12 patch_pymobiledevice3.py && sudo python3.13 patch_pymobiledevice3.py"

# Tailscale
check "Tailscale 已安装" "which tailscale || tailscale version" "https://tailscale.com/download"
check "Tailscale 运行中" "tailscale status" "打开 Tailscale app"

# iPhone 连通性
TS_IP="${1:-}"
if [ -n "$TS_IP" ]; then
  check "iPhone Tailscale 可达 ($TS_IP)" "ping -c 1 -t 3 $TS_IP" "确认 iPhone 上 Tailscale 开着"
  check "RemotePairing 端口 (49152)" "python3.12 -c \"
import socket; s=socket.socket(); s.settimeout(3)
s.connect(('$TS_IP',49152)); s.close()
\"" "iPhone WiFi 开关需要打开并连接网络"
else
  echo "  ⏭️  跳过 iPhone 连通性检查（用法: bash check.sh <TAILSCALE_IP>）"
fi

echo ""
echo "=== 结果: $OK 通过, $FAIL 失败 ==="
[ $FAIL -eq 0 ] && echo "🎉 全部就绪！可以运行 start_wda_remote.sh 了" || echo "⚠️  请修复上面标红的项目"
