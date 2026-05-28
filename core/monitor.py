import re
import sys
import time
import subprocess
import logging

from .console import console, Live, Table

log = logging.getLogger("throttnux")


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def format_bytes(b):
    """Convert bytes to human-readable string."""
    if b < 1024:
        return f"{b} B"
    elif b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 ** 3:
        return f"{b / 1024 ** 2:.1f} MB"
    return f"{b / 1024 ** 3:.2f} GB"


def get_tc_stats(interface):
    """
    Read tc stats for all throttle classes (1:10 and above).
    Returns aggregated (bytes_sent, pkts_sent, pkts_overlimit).
    """
    result = run(f"tc -s class show dev {interface}")
    lines  = result.stdout.splitlines()

    total_bytes    = 0
    total_pkts     = 0
    total_overlimit = 0
    found          = False

    for i, line in enumerate(lines):
        # Match class 1:10, 1:11, 1:12, etc (not 1:99 default)
        if re.search(r"class htb 1:([1-9][0-9]|[1-8][0-9])\b", line):
            for j in range(i + 1, min(i + 4, len(lines))):
                m = re.search(r"Sent (\d+) bytes (\d+) pkt.*overlimits (\d+)", lines[j])
                if m:
                    total_bytes     += int(m.group(1))
                    total_pkts      += int(m.group(2))
                    total_overlimit += int(m.group(3))
                    found            = True
                    break

    return (total_bytes, total_pkts, total_overlimit) if found else None


def verify_spoofing(interface, stop_event, status=None):
    """
    Auto-verify whether spoofing successfully captured target traffic.
    Returns (True, packet_count) if successful, or (False, 0) if failed.
    """
    messages = [
        "Initializing packet listener",
        "Intercepting active network pipes",
        "Evaluating target traffic routing",
        "Reading tc queue class counters",
        "Finalizing network state analysis"
    ]

    for i in range(5):
        if stop_event.is_set():
            return False, 0
        
        msg = messages[i]
        remaining = 5 - i
        if status:
            status.update(f"[bold yellow]Verifying packet capture: {msg} ({remaining}s remaining)...[/bold yellow]")
        
        time.sleep(1)

    if stop_event.is_set():
        return False, 0

    stats = get_tc_stats(interface)
    if stats:
        _, pkts, _ = stats
        if pkts > 0:
            return True, pkts
            
    return False, 0


def live_monitor(interface, targets, limit_mbps, stop_event):
    """
    Realtime bandwidth monitor menggunakan rich.live.
    Menampilkan data di dalam tabel statis yang terupdate setiap detik.
    """
    start_time = time.time()
    prev_bytes = 0
    prev_time  = time.time()

    print()

    with Live(console=console, refresh_per_second=1, transient=False) as live:
        while not stop_event.is_set():
            stats = get_tc_stats(interface)
            now = time.time()
            elapsed = now - prev_time
            uptime = int(now - start_time)
            uptime_str = f"{uptime // 3600:02d}:{(uptime % 3600) // 60:02d}:{uptime % 60:02d}"

            mbps = 0
            total_str = "0 B"
            status_icon = "○"

            if stats:
                total_bytes, _, overlimits = stats
                delta_bytes = max(0, total_bytes - prev_bytes)
                if elapsed > 0:
                    mbps = (delta_bytes * 8) / (elapsed * 1_000_000)
                total_str = format_bytes(total_bytes)
                status_icon = "●" if overlimits > 0 else "○"

                prev_bytes = total_bytes

            prev_time = now

            table = Table(box=None, show_header=False, expand=False)
            table.add_column("Status", style="bold red")
            table.add_column("IP")
            table.add_column("Speed")
            table.add_column("Data")
            table.add_column("Uptime")

            for tgt in targets:
                ip_addr = tgt["ip"] if isinstance(tgt, dict) else tgt
                table.add_row(
                    f"[LIVE {status_icon}]",
                    f"{ip_addr} →",
                    f"{mbps:.2f} Mbps / {limit_mbps} Mbps limit |",
                    f"{total_str} throttled |",
                    f"Uptime: {uptime_str}"
                )

            live.update(table)
            time.sleep(1)