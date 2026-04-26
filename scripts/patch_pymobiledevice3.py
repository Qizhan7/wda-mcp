#!/usr/bin/env python3
"""One-click patch for pymobiledevice3 — fixes xcuitest over remote (RSD) tunnels.
Run once after installing pymobiledevice3. Safe to re-run (skips if already patched).
See: https://github.com/doronz88/pymobiledevice3/pull/1665"""

import site, pathlib, sys

PATCH_LINE = '    OLD_SERVICE_NAME = "com.apple.testmanagerd.lockdown"'
PATCH_ADD = """\
    OLD_SERVICE_NAME = "com.apple.testmanagerd.lockdown"
    REGISTER_SERVICES = (
        XCTestManager_IDEInterface,
        XCTestManager_DaemonConnectionInterface,
        XCTestDriverInterface,
    )"""

patched = False
for base in site.getsitepackages() + [site.getusersitepackages()]:
    target = pathlib.Path(base) / "pymobiledevice3/services/dvt/testmanaged/xcuitest.py"
    if not target.exists():
        continue
    code = target.read_text()
    if "REGISTER_SERVICES" in code:
        print(f"Already patched: {target}")
        patched = True
        break
    if PATCH_LINE not in code:
        continue
    target.write_text(code.replace(PATCH_LINE, PATCH_ADD))
    print(f"Patched: {target}")
    patched = True
    break

if not patched:
    print("pymobiledevice3 not found. Install it first:")
    print("  python3.12 -m pip install pymobiledevice3")
    print("  python3.13 -m pip install pymobiledevice3")
    sys.exit(1)
