import re
import sys
import time
import logging
import subprocess

from core.console import console

try:
    import psutil
except ImportError:
    print("[ERROR] Environment configuration unfulfilled.")
    print("        Please ensure you have initialized the project using: sudo ./setup.sh")
    print("        To execute Throttnux safely, run: sudo .venv/bin/python3 main.py")
    sys.exit(1)


log = logging.getLogger("throttnux")


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def get_active_interfaces():
    """
    Return list of active non-loopback interfaces with an assigned IP,
    using psutil — works across all Linux distros.
    """
    interfaces = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    for iface, stat in stats.items():
        if iface == "lo":
            continue
        if not stat.isup:
            continue
        if iface not in addrs:
            continue

        ipv4 = [
            a.address for a in addrs[iface]
            if a.family.name == "AF_INET"
        ]
        if not ipv4:
            continue

        interfaces.append({
            "name":  iface,
            "ip":    ipv4[0],
            "speed": f"{stat.speed} Mbps" if stat.speed > 0 else "unknown speed"
        })

    # =========================================================
    # ⚠️ DUMMY 
    # =========================================================
    # interfaces.extend([
    #     {"name": "eth0",    "ip": "192.168.1.10", "speed": "1000 Mbps"},
    #     {"name": "docker0", "ip": "172.17.0.1",   "speed": "unknown speed"},
    #     {"name": "tun0",    "ip": "10.8.0.2",     "speed": "10 Mbps"}
    # ])
    # =========================================================
    # ⚠️ DUMMY DATA END
    # =========================================================

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

    # =========================================================
    # ⚠️ DUMMY DATA START 
    # =========================================================
    # gateways.extend([
    #     {"ip": "192.168.1.1", "interface": "eth0"},
    #     {"ip": "172.17.0.1",  "interface": "docker0"},
    #     {"ip": "10.8.0.1",    "interface": "tun0"}
    # ])
    # =========================================================
    # ⚠️ DUMMY DATA END
    # =========================================================

    return gateways


def pick_interface(prompt_fn):
    """Interactive interface picker with a sleek scanning spinner."""
    with console.status("Scanning interfaces...", spinner="dots") as status:
        time.sleep(1.2)
        status.update("Filtering active interfaces...")
        time.sleep(0.8)

    interfaces = get_active_interfaces()

    if not interfaces:
        log.error("No active network interfaces found.")
        sys.exit(1)
    
    console.print(f" [success]Found {len(interfaces)} active interface(s)[/success]")
        
    if len(interfaces) == 1:
        iface = interfaces[0]
        console.print(f" [not bold white]Auto-selected interface: {iface['name']} ({iface['ip']})[/not bold white]")
        return iface["name"]

    print("")
    print("  Available network interfaces:")
    print("")
    print(f"  {'No':<5} {'Interface':<14} {'IP Address':<18} {'Speed'}")

    for i, iface in enumerate(interfaces, 1):
        print(f"  {i:<5} {iface['name']:<14} {iface['ip']:<18} {iface['speed']}")

    print("=" * 55)

    idx      = prompt_fn("\n  Select interface number: ", valid_range=len(interfaces))
    selected = interfaces[idx]
    console.print(f"Selected interface: {selected['name']} ({selected['ip']})")
    return selected["name"]


def pick_router(interface, prompt_fn):
    """Interactive router/gateway picker with a routing query spinner."""
    gateways   = get_gateways()
    matched    = [g for g in gateways if g["interface"] == interface]
    candidates = matched if matched else gateways

    if not candidates:
        log.error("No gateway detected. Make sure you are connected to a network.")
        sys.exit(1)

    if len(candidates) == 1:
        gw = candidates[0]["ip"]
        console.print(f" [not bold white]Auto-selected gateway: {gw}[/not bold white]")
        return gw

    with console.status("[bold cyan]Querying kernel routing table for available gateways...[/bold cyan]", spinner="dots"):
        time.sleep(1.2)

    print("\n" + "=" * 55)
    print("  Available gateways (routers):")
    print("=" * 55)
    print(f"  {'No':<5} {'Gateway IP':<18} {'Interface'}")
    print("  " + "-" * 40)

    for i, gw in enumerate(candidates, 1):
        print(f"  {i:<5} {gw['ip']:<18} {gw['interface']}")

    print("=" * 55)

    idx      = prompt_fn("\n  Select gateway number: ", valid_range=len(candidates))
    selected = candidates[idx]["ip"]
    console.print(f"Selected gateway: {selected}")
    return selected