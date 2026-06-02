import os
import sys
import shutil
import logging

from .console import console

log = logging.getLogger("throttnux")

REQUIRED_TOOLS = ["arpspoof", "tc", "arp-scan"]

def check_os():
    if sys.platform != "linux":
        console.print(" [error]Throttnux only supports Linux.[/error]")
        console.print(" [error]Windows and macOS are not supported.[/error]")
        sys.exit(1)


def check_root():
    if os.geteuid() != 0:
        console.print(f" [error]This script must be run as root.[/error]")
        console.print(f" [error]Try: sudo throttnux[/error]")
        sys.exit(1)


def check_dependencies():
    missing = []
    for tool in REQUIRED_TOOLS:
        if not shutil.which(tool):
            missing.append(tool)

    if missing:
        console.print(f" [error]Missing required core tools: {', '.join(missing)}[/error]")
        console.print(f" [error]Please install the missing tools using your system package manager (e.g., apt, dnf, pacman).[/error]")
        sys.exit(1)