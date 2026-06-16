import re
import sys
import subprocess
import logging
import questionary
import ipaddress

from .console import (
    console,
    Table,
    box,
    qselect
    )

log = logging.getLogger("throttnux")


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def scan_devices(interface, router_ip, status_msg="Scanning network for active devices..."):
    """Scan all active devices on the local network using arp-scan."""
    with console.status(status_msg, spinner="dots"):
        result = run(f"arp-scan --localnet -I {interface}")

        devices = []
        for line in result.stdout.splitlines():
            match = re.match(r"(\d+\.\d+\.\d+\.\d+)\s+([\w:]+)\s*(.*)", line)
            if match:
                ip, mac, vendor = match.groups()
                if ip == router_ip:
                    continue
                
                vendor_clean = vendor.strip()

                if not vendor_clean or "locally administered" in vendor_clean.lower():
                    vendor_name = "Unknown"
                else:
                    vendor_name = vendor_clean
                
                devices.append({
                    "ip":     ip,
                    "mac":    mac.lower(),
                    "vendor": vendor_name
                    })
        
        devices.sort(key=lambda dev:ipaddress.ip_address(dev["ip"]))
        
        if not devices:
            console.print(" [error]No devices found on the network.[/error]")
            sys.exit(1)
        else:
            console.print(f" [success]Found {len(devices)} devices detected on network[/success]")
        
        return devices


def display_devices(devices, last_ips=None):
    table = Table(box=box.HORIZONTALS, title_style="bold", show_header=True)
    table.add_column("IP Address",  style="")
    table.add_column("MAC Address", style="")
    table.add_column("Device",      style="")

    
    last_ips = last_ips or []
    
    for dev in devices:
        is_last   = dev["ip"] in last_ips
        
        vendor = dev.get("vendor", "unknown")
        if len(vendor) > 25:
            vendor = vendor[:25]
        
        ip_cell     = f"[bold]{dev['ip']}[/bold]" if is_last else dev["ip"]
        mac_cell    = f"[bold]{dev['mac']}[/bold]" if is_last else dev["mac"]
        vendor_cell = f"[bold]{vendor}[/bold]" if is_last else vendor
    
        table.add_row(ip_cell, mac_cell, vendor_cell)
      
    
    console.print(table)


def pick_limit(prompt_fn=None):
    """Prompt user to select a bandwidth limit."""
    
    choice = qselect(
        "Select bandwidth limit:",
        choices=[
            questionary.Choice("1 Mbps — Heavy buffering, no HD YouTube",  value="1"),
            questionary.Choice("2 Mbps — Stuck at 480p",                   value="2"),
            questionary.Choice("3 Mbps — Occasional buffering at 720p",    value="3"),
            questionary.Choice("Custom",                                    value="4")
            ]
        )
    
    if choice is None:
        console.print(" [error]Cancelled by user.[/error]")
        sys.exit(0)
        
    presets = {"1": 1.0, "2": 2.0, "3": 3.0}
    
    if choice in presets:
        limit_value = presets[choice]
        return limit_value
        
    if choice == "4":
        while True:
            try:
                console.print()
                console.print(
                "[dim]"
                "  • Enter bandwidth limit in Mbps\n"
                "  • Use decimals (.) for values below 1 Mbps (e.g. 0.1, 0.10)\n"
                "  • Recommended range: 0.5 - 20 Mbps\n"
                "[/dim]"
                )

                val = float(input("  Enter limit in Mbps: ").strip())

                if val <= 0:
                    console.print("  [error]Limit must be greater than 0.0 Mbps.[/error]")
                    continue
                
                return val

            except ValueError:
                console.print("  [error]Invalid input. Please enter a valid decimal number.[/error]")
            except KeyboardInterrupt:
                console.print(" [error]Cancelled by user.[/error]")
                sys.exit(0)