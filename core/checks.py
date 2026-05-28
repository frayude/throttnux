import os
import sys
import shutil
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
        log.error("Try: sudo throttnux")
        sys.exit(1)


def check_dependencies():
    missing = []
    for tool in REQUIRED_TOOLS:
        if not shutil.which(tool):
            missing.append(tool)

    if missing:
        log.error(f"Missing required core tools: {', '.join(missing)}")
        log.error("Please install the missing tools using your system package manager (e.g., apt, dnf, pacman).")
        sys.exit(1)