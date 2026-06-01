import re
import sys
import logging
import subprocess
import psutil

from core.console import console, questionary, qselect


log = logging.getLogger("throttnux")


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def get_active_interfaces():
    interfaces = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    for iface, stat in stats.items():
        if iface == "lo" or not stat.isup or iface not in addrs:
            continue

        ipv4 = [a.address for a in addrs[iface] if a.family.name == "AF_INET"]
        mac  = [a.address for a in addrs[iface] if a.family.name == "AF_PACKET"]
        
        if not ipv4 or not mac:
            continue

        interfaces.append({
            "name":  iface,
            "ip":    ipv4[0],
            "mac":   mac[0].lower()
        })

    return interfaces


def get_gateways():
    """
    Detect available gateways from the system routing table.
    Returns list of gateway IPs associated with each interface.
    """
    gateways = []
    result = run("ip route show")

    for line in result.stdout.splitlines():
        match = re.match(r"default via (\S+) dev (\S+)", line)
        if match:
            gw_ip, iface = match.groups()
            gateways.append({"ip": gw_ip, "interface": iface})

    return gateways


def pick_interface():
    interfaces = get_active_interfaces()
    
    if not interfaces:
        console.print(" [error]No active network interfaces found.[/error]")
        sys.exit(1)
    
    console.print(f" [success]Found {len(interfaces)} active interface(s)[/success]")
        
    if len(interfaces) == 1:
        iface = interfaces[0]
        console.print(f" [text]Auto-selected interface: {iface['name']} ({iface['ip']})[/text]")
        return iface["name"]

    choices = []
    
    for iface in interfaces:
        display_line = f"{iface['name']:<12} {iface['ip']:<16} {iface['mac']}"
        choices.append(questionary.Choice(title=display_line, value=iface["name"]))
    
    selected_name = qselect(
        "Select network interface:",
        choices=choices
    )

    if selected_name is None:
        console.print(" [error]Cancelled by user.[/error]")
        sys.exit(0)

    selected_iface = next(i for i in interfaces if i["name"] == selected_name)
    console.print(f" [text]Selected interface: {selected_iface['name']}[/text]")
    
    return selected_name
        

def pick_router(interface):
    """router/gateway picker matching the pick_interface style."""
    gateways   = get_gateways()
    matched    = [g for g in gateways if g["interface"] == interface]
    candidates = matched if matched else gateways

    if not candidates:
        console.print(" [error]No gateway detected. Make sure you are connected to a network.[/error]")
        sys.exit(1)

    if len(candidates) == 1:
        gw = candidates[0]["ip"]
        console.print(f" [text]Auto-selected gateway: {gw}[/text]")
        return gw

    choices = []
    
    for gw in candidates:
        display_line = f"{gw['ip']:<18} {gw['interface']}"
        choices.append(questionary.Choice(title=display_line, value=gw["ip"]))
    
    selected_gw = qselect(
        "Select gateway router:",
        choices=choices
    )

    if selected_gw is None:
        console.print(" [error]Cancelled by user.[/error]")
        sys.exit(0)

    console.print(f" [text]Selected gateway: {selected_gw}[/text]")
    
    return selected_gw