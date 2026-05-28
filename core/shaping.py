import subprocess
import logging

log = logging.getLogger("throttnux")

# System kernel parameter to control the system forward IPv4 packets
# Every Linux-based system have this
SYSCTL_IP_FORWARD_PATH = "/proc/sys/net/ipv4/ip_forward"


def run(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        log.error(f"Command failed: {cmd}\n{result.stderr.strip()}")
    return result


def enable_ip_forward():
    run(f"echo 1 > {SYSCTL_IP_FORWARD_PATH}")


def disable_ip_forward():
    run(f"echo 0 > {SYSCTL_IP_FORWARD_PATH}")


def setup_traffic_shaping(interface, targets, limit_mbps, status=None):
    """
    Setup tc HTB for one or multiple targets.
    targets: list of dicts with "ip" key, or single IP string.
    Each target gets its own class ID: 1:10, 1:11, 1:12, ...
    """
    # Normalize to list
    if isinstance(targets, str):
        targets = [{"ip": targets}]

    limit_kbit = int(limit_mbps * 1000)

    run(f"tc qdisc del dev {interface} root", check=False)
    run(f"tc qdisc add dev {interface} root handle 1: htb default 99")
    run(f"tc class add dev {interface} parent 1: classid 1:99 htb rate 1000mbit")

    for i, tgt in enumerate(targets):
        ip       = tgt["ip"] if isinstance(tgt, dict) else tgt
        class_id = 10 + i
        run(f"tc class add dev {interface} parent 1: classid 1:{class_id} htb rate {limit_kbit}kbit burst 10k")
        run(f"tc filter add dev {interface} parent 1: protocol ip prio {i*2+1} u32 match ip dst {ip}/32 flowid 1:{class_id}")
        run(f"tc filter add dev {interface} parent 1: protocol ip prio {i*2+2} u32 match ip src {ip}/32 flowid 1:{class_id}")


def cleanup_traffic_shaping(interface):
    run(f"tc qdisc del dev {interface} root", check=False)