#!/usr/bin/env bash
set -e
WDA_DIR="${WDA_PROJECT_DIR:-$HOME/Desktop/WebDriverAgent}"
DEVICE="${WDA_DEVICE_ID:?Set WDA_DEVICE_ID environment variable}"
echo "==> Rebuilding WDA for device $DEVICE ..."
cd "$WDA_DIR"
xcodebuild build-for-testing -project WebDriverAgent.xcodeproj -scheme WebDriverAgentRunner -destination "id=$DEVICE" -allowProvisioningUpdates
echo "==> Build done. Starting WDA ..."
pkill -f "xcodebuild.*test-without-building" 2>/dev/null || true
nohup xcodebuild test-without-building -project WebDriverAgent.xcodeproj -scheme WebDriverAgentRunner -destination "id=$DEVICE" > /tmp/wda_run.log 2>&1 &
echo "==> WDA starting in background. Check /tmp/wda_run.log"
