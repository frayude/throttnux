#!/usr/bin/env python3

import sys
import signal
import logging
import threading
import time

from core.console import console
from pyfiglet import figlet_format

from core import (
    check_os,
    check_root,
    check_dependencies,
    pick_interface,
    pick_router,
    scan_devices,
    display_devices,
    pick_limit,
    enable_ip_forward,
    disable_ip_forward,
    setup_traffic_shaping,
    cleanup_traffic_shaping,
    arp_spoof_loop,
    verify_spoofing,
    live_monitor,
    save_config,
    load_config,
    prompt_use_saved_config,
    prompt_operational_mode,
    prompt_blacklist_selection,
    prompt_whitelist_selection,
    prompt_session_review,
    match_saved_config
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("throttnux")

stop_event = threading.Event()


def prompt(text, valid_range=None):
    """Generic prompt with optional range validation."""
    while True:
        try:
            choice = input(text).strip()
            if valid_range is not None:
                idx = int(choice) - 1
                if 0 <= idx < valid_range:
                    return idx
                print(f"  [!] Enter a number between 1 and {valid_range}")
            else:
                return choice
        except ValueError:
            print("  [!] Invalid input.")
        except KeyboardInterrupt:
            print("\n  Cancelled.")
            sys.exit(0)


def banner():
    print()    
    print(figlet_format("Throttnux", font="standard").rstrip())
    console.print("  [dim]Per-device bandwidth limiter via ARP spoofing[/dim]")
    print()    


def signal_handler(sig, frame):
    stop_event.set()


def main():
    check_os()
    check_root()
    check_dependencies()

    banner()

    interface  = None
    router_ip  = None
    limit_mbps = None
    used_saved = False
    targets_to_throttle = []
    
    interface = pick_interface()
    router_ip = pick_router(interface)

    config  = load_config()
    devices = scan_devices(interface, router_ip)

    # 1. Validate targets with live network data before rendering
    matched_dev = match_saved_config(config, devices)
    operational_mode = None
    
    if matched_dev:
        last_ips = [d["ip"] for d in matched_dev]
        last_limit = config.get("limit_mbps")
    else:
        last_ips = []
        last_limit = None
    
    # 2. Render UI table with accurate pointers
    display_devices(devices, last_ips=last_ips, last_limit_mbps=last_limit)
    
    if matched_dev and config.get("interface") == interface and config.get("router_ip") == router_ip:
        action = prompt_use_saved_config(config, matched_dev)

        while action == "rescan":
            console.clear()
            console.print()
            
            devices = scan_devices(interface, router_ip, status_msg="Rescanning network, please wait...")
            
            # Re-validate dynamically on rescan
            matched_dev = match_saved_config(config, devices)
            if matched_dev:
                last_ips_rescan = [d["ip"] for d in matched_dev]
                display_devices(devices, last_ips=last_ips_rescan, last_limit_mbps=last_limit)
                action = prompt_use_saved_config(config, matched_dev)
            else:
                display_devices(devices, last_ips=[], last_limit_mbps=None)
                action = "new_scan"
                break
        
        if action == "use_saved":
            limit_mbps = config["limit_mbps"]
            operational_mode = config.get("operational_mode", "blacklist")
            targets_to_throttle = matched_dev
            used_saved = True
        elif action == "new_scan":
            operational_mode = prompt_operational_mode()
    else:
        console.print(" [dim]No previous session found on this network.[/dim]\n")
        operational_mode = prompt_operational_mode()


    if not used_saved:
        if operational_mode == "blacklist" or operational_mode is None:
            targets_to_throttle = prompt_blacklist_selection(devices, matched_dev)

        elif operational_mode == "whitelist":
            safe_devices = prompt_whitelist_selection(devices, matched_dev)
            safe_ips = [d["ip"] for d in safe_devices]
            
            targets_to_throttle = [d for d in devices if d["ip"] not in safe_ips]

            if not targets_to_throttle:
                print("  [!] No targets to throttle. Everyone is whitelisted.")
                sys.exit(0)
                
        limit_mbps = pick_limit(prompt)
        
    if not used_saved:
        prompt_session_review(interface, router_ip, operational_mode, limit_mbps, targets_to_throttle)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    spoof_threads = []
    success = False

    try:
        with console.status("Initializing network routing...", spinner="dots") as status:
            mode_display = operational_mode.capitalize() if operational_mode else "Blacklist"
            status.update(f"Saving {mode_display} config for {len(targets_to_throttle)} target(s) to config.json...")
        
            save_config(interface, router_ip, operational_mode, targets_to_throttle, limit_mbps, status=status)
            time.sleep(0.8)
            
            status.update("System: Forcing net.ipv4.ip_forward=1...")
            enable_ip_forward()
            time.sleep(0.8)
            
            status.update(f"QoS: Attaching {limit_mbps} Mbps HTB rules to interface {interface}...")
            setup_traffic_shaping(interface, targets_to_throttle, limit_mbps)
                
            time.sleep(0.8)
            
            status.update(f"ARP: Injecting MITM routes between {len(targets_to_throttle)} target(s) and gateway {router_ip}...")
            for tgt in targets_to_throttle:
                t = threading.Thread(
                    target=arp_spoof_loop,
                    args=(interface, tgt["ip"], router_ip, stop_event),
                    daemon=True
                )
                t.start()
                spoof_threads.append(t)
            time.sleep(0.8)
            
            success, captured_pkts = verify_spoofing(interface, stop_event, status=status)
            
            if not success:
                stop_event.set()

        if success:
            console.print(f" [success]Spoofing successful! {captured_pkts} packets captured. Launching live monitor...[/success]")
            time.sleep(1.5)
            console.print()
            monitor_thread = threading.Thread(
                target=live_monitor,
                args=(interface, targets_to_throttle, limit_mbps, stop_event),
                daemon=True
            )
            monitor_thread.start()
        else:
            console.print("  [error]Target device does not appear to be using the network. Stopping...[/error]")

        try:
            while not stop_event.is_set():
                stop_event.wait(0.1)
        except KeyboardInterrupt:
            stop_event.set()

        if success and 'monitor_thread' in locals():
            monitor_thread.join(timeout=2)

    finally:
        with console.status("Initiating teardown sequence...", spinner="dots") as status:

            status.update(f"Teardown: Terminating active ARP spoofing threads for {len(spoof_threads)} thread(s)...")
            for t in spoof_threads:
                t.join(timeout=5)
            time.sleep(0.6)

            status.update(f"QoS: Flushing HTB shaping rules from interface {interface}...")
            cleanup_traffic_shaping(interface)
            time.sleep(0.6)

            status.update("System: Restoring net.ipv4.ip_forward=0...")
            disable_ip_forward()
            time.sleep(0.6)

        console.print("\n [error]Session terminated.[/error]")
        console.print(" [success]Network restored and traffic shaping rules cleared.[/success]")


if __name__ == "__main__":
    main()