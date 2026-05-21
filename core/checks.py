import os
import sys
import subprocess
import logging

log = logging.getLogger("throttnux")

REQUIRED_TOOLS = ["arpspoof", "tc", "arp-scan"]

def check_os():
    if sys.platform != "linux":
        log.error("Throttnux only supports Linux.")
        log.error("Windows and macOS are not supported.")
        sys.exit(1)


def check_root():
    if os.geteuid() != 0:
        log.error("This script must be run as root.")
        log.error("Try: sudo python3 main.py")
        sys.exit(1)


def check_dependencies():
    missing = []
    for tool in REQUIRED_TOOLS:
        result = subprocess.run(
            f"command -v {tool} 2>&1 >/dev/null",
            shell=True,
            # FIXME: This line is unnecessary if we want to get the return code
            capture_output=True
        )
        if result.returncode != 0:
            missing.append(tool)

    if missing:
        log.error(f"Missing required core tools: {', '.join(missing)}")
        log.error("Please execute the installer script to automatically resolve dependencies:")
        log.error("Try: sudo ./setup.sh")
        sys.exit(1)