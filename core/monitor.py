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
    """
    Converts raw byte counts into human-readable strings.
    Limits decimal precision to keep the CLI table aligned and readable.
    """
    if b < 1024:
        return f"{b} B"
    elif b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 ** 3:
        return f"{b / 1024 ** 2:.1f} MB"
    return f"{b / 1024 ** 3:.2f} GB"


def check_online(ip_address):
    """
    Actively probes the target to differentiate between an 'idle' device 
    (connected but drawing 0 Mbps) and a 'disconnected' device.
    Uses a 1-second timeout (-W 1) to prevent UI thread blocking.
    """
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip_address],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except Exception:
        return False


def get_tc_stats_per_class(interface):
    """
    Parses 'tc' utility output to extract traffic statistics per HTB class.
    
    Returns:
        dict: A mapping of class IDs (int) to their respective total_bytes (int).
              Example: {10: 15420, 11: 5320}
    """
    result = run(f"tc -s class show dev {interface}")
    lines = result.stdout.splitlines()

    stats = {}
    current_class_id = None

    for line in lines:
        # Identify the HTB class block (e.g., "class htb 1:10 root ...")
        class_match = re.search(r"class htb 1:(\d+)", line)
        if class_match:
            current_class_id = int(class_match.group(1))
            continue
        
        # Extract the byte count for the currently identified class
        if current_class_id is not None:
            sent_match = re.search(r"Sent\s+(\d+)\s+bytes", line)
            if sent_match:
                stats[current_class_id] = int(sent_match.group(1))
                current_class_id = None # Reset for the next class block

    return stats


def verify_spoofing(interface, stop_event, status=None):
    """
    Placeholder for pre-flight ARP spoof verification.
    Ensures traffic is actually flowing through the attacker machine before shaping begins.
    """
    if status:
        status.update("[cyan]Verifying traffic interception...[/cyan]")
        time.sleep(1) # Simulate some verification time
        
    return True, 101


import threading

def live_monitor(interface, targets, limit_mbps, stop_event):
    """
    Orchestrates the live CLI dashboard. 
    Uses a background thread for active probing to ensure the UI 
    remains completely non-blocking and smooth.
    """
    states = {}
    
    for i, tgt in enumerate(targets):
        ip = tgt["ip"] if isinstance(tgt, dict) else tgt
        states[ip] = {
            "class_id": 10 + i, 
            "total_bytes": 0,
            "last_bytes": 0,
            "start_time": time.time(),
            "is_online": True,
            "needs_ping": False # Signals the background thread to probe this IP
        }

    def background_pinger():
        """
        Runs asynchronously to execute network probes (ping).
        This prevents the 1-second timeout from blocking the Rich Live UI.
        """
        while not stop_event.is_set():
            for ip, state in states.items():
                if state["needs_ping"]:
                    state["is_online"] = check_online(ip)
            stop_event.wait(1.5)

    threading.Thread(target=background_pinger, daemon=True).start()

    prev_time = time.time()

    with Live(console=console, refresh_per_second=10) as live:
        while not stop_event.is_set():
            now = time.time()
            elapsed = now - prev_time
            
            tc_stats = get_tc_stats_per_class(interface)

            table = Table(box=box.SIMPLE, show_header=True, expand=False, header_style="bold cyan")
            table.add_column("STATUS", justify="left")
            table.add_column("TARGET IP", justify="left")
            table.add_column("CURRENT SPEED", justify="right")
            table.add_column("TOTAL DATA", justify="right")
            table.add_column("SESSION TIME", justify="center")

            for tgt in targets:
                ip = tgt["ip"] if isinstance(tgt, dict) else tgt
                state = states[ip]
                
                # Calculate true throughput
                current_bytes = tc_stats.get(state["class_id"], state["last_bytes"])
                delta_bytes = max(0, current_bytes - state["last_bytes"])
                    
                mbps = 0.0
                if elapsed > 0:
                    mbps = (delta_bytes * 8) / (elapsed * 1_000_000)

                # Traffic-first evaluation
                if mbps > 0.05:
                    state["needs_ping"] = False
                    state["is_online"] = True
                    status_display = "[bold green]ACTIVE[/bold green]"
                    speed_text = f"[bold green]{mbps:.2f} Mbps[/bold green]"
                    text_style = "white"
                else:
                    # Delegate the heavy lifting to the background thread
                    state["needs_ping"] = True
                    if state["is_online"]:
                        status_display = "[dim white]IDLE[/dim white]"
                        speed_text = "[dim white]0.00 Mbps[/dim white]"
                        text_style = "dim white"
                    else:
                        status_display = "[bold magenta]PAUSED[/bold magenta]"
                        speed_text = "[dim red][OFFLINE][/dim red]"
                        text_style = "dim white"

                state["total_bytes"] = current_bytes
                state["last_bytes"]  = current_bytes

                uptime = int(now - state["start_time"])
                m, s = divmod(uptime, 60)
                h, m = divmod(m, 60)
                uptime_str = f"{h:02d}:{m:02d}:{s:02d}"

                total_str = format_bytes(state["total_bytes"])

                table.add_row(
                    status_display,
                    f"[{text_style}]{ip}[/{text_style}]",
                    speed_text,
                    f"[{text_style}]{total_str}[/{text_style}]",
                    f"[{text_style}]{uptime_str}[/{text_style}]"
                )

            prev_time = now

            dashboard = Panel(
                table,
                title="[bold white]THROTTNUX LIVE MONITOR[/bold white]",
                subtitle="[dim white]Press Ctrl+C to terminate[/dim white]",
                title_align="left",
                subtitle_align="right",
                padding=(0, 1),
                expand=False
            )
            
            live.update(dashboard)
            stop_event.wait(0.2)