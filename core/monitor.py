import re
import time
import subprocess
import logging
import threading

from rich import box
from rich.panel import Panel
from .console import console, Live, Table

log = logging.getLogger("throttnux")


def run(cmd):
    """Executes a shell command and captures its standard output."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def format_bytes(b):
    """Converts raw byte counts into human-readable strings."""
    if b < 1024:
        return f"{b} B"
    elif b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 ** 3:
        return f"{b / 1024 ** 2:.1f} MB"
    return f"{b / 1024 ** 3:.2f} GB"


def check_online(interface, ip_address):
    """
    Checks if a device is reachable via ARP — more reliable than ping
    since many devices block ICMP but always respond to ARP requests.
    Falls back to ARP cache check if arping is unavailable.
    """
    # Primary: arping via ARP request (works even on devices that block ICMP)
    try:
        result = subprocess.run(
            ["arping", "-c", "1", "-W", "1", "-I", interface, ip_address],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass

    # Fallback: check OS ARP cache
    try:
        result = run(f"ip neigh show {ip_address}")
        output = result.stdout.strip()
        if output and "FAILED" not in output and "INCOMPLETE" not in output:
            return True
    except Exception:
        pass

    return False


def get_tc_stats_per_class(interface):
    """
    Parses tc output to extract traffic statistics per HTB class.

    Returns:
        dict: Mapping of class IDs (int) to total_bytes (int).
              Example: {10: 15420, 11: 5320}
    """
    result = run(f"tc -s class show dev {interface}")
    lines  = result.stdout.splitlines()

    stats            = {}
    current_class_id = None

    for line in lines:
        class_match = re.search(r"class htb 1:(\d+)", line)
        if class_match:
            current_class_id = int(class_match.group(1))
            continue

        if current_class_id is not None:
            sent_match = re.search(r"Sent\s+(\d+)\s+bytes", line)
            if sent_match:
                stats[current_class_id] = int(sent_match.group(1))
                current_class_id = None

    return stats


def verify_spoofing(interface, stop_event, status=None):
    """
    Verifies ARP spoofing is working by checking if traffic is flowing
    through tc classes. Waits up to 5 seconds for packets to appear.
    Returns (True, packet_count) if successful, (False, 0) if not.
    """
    if status:
        status.update("Verifying traffic interception (timeout 5s)...")
        time.sleep(5)
    for _ in range(5):
        if stop_event.is_set():
            return False, 0
        
        result = run(f"tc -s class show dev {interface}")
        lines = result.stdout.splitlines()
        
        total_pkts = 0
        for idx, line in enumerate(lines):
            if "class htb 1:" in line:
                if idx + 1 < len(lines):
                    m = re.search(r"Sent \d+ bytes (\d+) pkt", lines[idx + 1])
                    if m:
                        total_pkts += int(m.group(1))

        if total_pkts > 0:
            return True, total_pkts
            
        time.sleep(1)

    return False, 0


def live_monitor(interface, targets, limit_mbps, stop_event):
    """
    Orchestrates the live CLI dashboard.
    Uses a background thread for ARP probing to keep UI non-blocking.
    Uses threading.Lock to prevent race conditions on shared state.
    """
    states      = {}
    states_lock = threading.Lock()

    for i, tgt in enumerate(targets):
        ip = tgt["ip"] if isinstance(tgt, dict) else tgt
        states[ip] = {
            "class_id":   10 + i,
            "total_bytes": 0,
            "last_bytes":  0,
            "start_time":  time.time(),
            "is_online":   True,
            "needs_probe": False,
        }

    def background_prober():
        """
        Runs ARP probes asynchronously for IPs that need connectivity check.
        Uses Lock to safely update shared state.
        """
        while not stop_event.is_set():
            with states_lock:
                ips_to_probe = [
                    ip for ip, state in states.items()
                    if state["needs_probe"]
                ]

            for ip in ips_to_probe:
                if stop_event.is_set():
                    break
                is_online = check_online(interface, ip)
                with states_lock:
                    if ip in states:
                        states[ip]["is_online"]   = is_online
                        states[ip]["needs_probe"] = False

            stop_event.wait(2)

    threading.Thread(target=background_prober, daemon=True).start()

    prev_time = time.time()

    with Live(console=console, refresh_per_second=2) as live:
        while not stop_event.is_set():
            now     = time.time()
            elapsed = now - prev_time

            tc_stats = get_tc_stats_per_class(interface)

            table = Table(
                box=box.SIMPLE,
                show_header=True,
                expand=False,
            )
            table.add_column("STATUS",        justify="left")
            table.add_column("TARGET IP",     justify="left")
            table.add_column("LIMIT SPEED",     justify="right")
            table.add_column("CURRENT SPEED", justify="right")
            table.add_column("TOTAL DATA",    justify="right")
            table.add_column("SESSION TIME",  justify="center")

            with states_lock:
                for tgt in targets:
                    ip    = tgt["ip"] if isinstance(tgt, dict) else tgt
                    state = states[ip]

                    current_bytes = tc_stats.get(state["class_id"], state["last_bytes"])
                    delta_bytes   = max(0, current_bytes - state["last_bytes"])

                    mbps = 0.0
                    if elapsed > 0:
                        mbps = (delta_bytes * 8) / (elapsed * 1_000_000)

                    # Traffic-first: if traffic flowing, device is definitely online
                    if mbps > 0.05:
                        state["needs_probe"] = False
                        state["is_online"]   = True
                        status_display       = "[bold green]ACTIVE[/bold green]"
                        speed_text           = f"[bold green]{mbps:.2f} Mbps[/bold green]"
                        text_style           = "white"
                    else:
                        # No traffic — delegate reachability check to background prober
                        state["needs_probe"] = True
                        if state["is_online"]:
                            status_display = "[dim white]IDLE[/dim white]"
                            speed_text     = "[dim white]0.00 Mbps[/dim white]"
                            text_style     = "dim white"
                        else:
                            status_display = "[bold magenta]PAUSED[/bold magenta]"
                            speed_text     = "[dim red][OFFLINE][/dim red]"
                            text_style     = "dim white"

                    state["total_bytes"] = current_bytes
                    state["last_bytes"]  = current_bytes

                    uptime     = int(now - state["start_time"])
                    m, s       = divmod(uptime, 60)
                    h, m       = divmod(m, 60)
                    uptime_str = f"{h:02d}:{m:02d}:{s:02d}"
                    total_str  = format_bytes(state["total_bytes"])

                    table.add_row(
                        status_display,
                        f"[{text_style}]{ip}[/{text_style}]",
                        f"[{text_style}]{limit_mbps} Mbps[/{text_style}]",
                        speed_text,
                        f"[{text_style}]{total_str}[/{text_style}]",
                        f"[{text_style}]{uptime_str}[/{text_style}]",
                    )

            prev_time = now

            live.update(Panel(
                table,
                subtitle="[dim white]Press Ctrl+C to terminate[/dim white]",
                title_align="left",
                subtitle_align="right",
                padding=(0, 1),
                expand=False,
            ))

            stop_event.wait(0.5)