import json
import os
import logging
import sys
import questionary


from .console import (custom_style,
                      console,
                      Panel,
                      Group,
                      qselect)

log = logging.getLogger("throttnux")

CONFIG_DIR  = os.path.expanduser("~/.config/throttnux")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def save_config(interface, router_ip, mode, targets, limit_mbps, status=None):
    """Save last session config to ~/.config/throttnux/config.json."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    config = {
        "interface":        interface,
        "router_ip":        router_ip,
        "operational_mode": mode,
        "targets":          targets,
        "limit_mbps":       limit_mbps,
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        
        if status:
            status.update(f"Config saved to {CONFIG_FILE}")
        else:
            status.update(f"Config saved to {CONFIG_FILE}")
            
    except Exception as e:
        log.warning(f"Failed to save config: {e}")


def load_config():
    """Load config from ~/.config/throttnux/config.json if it exists."""
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"Failed to load config: {e}")
        return None


def match_saved_config(config, devices):
    """
    Check if saved config target IP is present in current network scan.
    Returns the matched device dict or None.
    """
    if not config:
        return None
    
    saved_ips = []
    if "targets" in config:
        saved_ips = [t["ip"] for t in config["targets"]]
    elif "target_ip" in config:
        saved_ips = [config["target_ip"]]
    
    matched = [d for d in devices if d["ip"] in saved_ips]
    return matched if matched else None
    
    
def prompt_use_saved_config(config):
    """Ask user if they want to use the saved config."""
    mode_str = config.get("operational_mode", "Blacklist").capitalize()
    limit = config.get("limit_mbps", 1.0)
    
    console.print(f" [text]Last session : {mode_str} - {limit} Mbps[/text]")
    
   
    ip_list = []
    if "targets" in config:
        ip_list = [tgt["ip"] for tgt in config["targets"]]
    elif "target_ip" in config:
        ip_list = [config["target_ip"]]
        
    
    max_ip_len = max([len(ip) for ip in ip_list]) if ip_list else 0
    
    if "targets" in config:
        for tgt in config["targets"]:
            vendor = tgt.get("vendor", "Unknown")
            if not vendor or "locally administered" in vendor.lower():
                vendor = "Unknown"
            
            if len(vendor) > 25:
                vendor = vendor[:25]
            
            console.print(f"   [text]{tgt['ip']:<{max_ip_len}}  • {vendor}[/text]")
            
    elif "target_ip" in config:
        vendor = config.get("target_vendor", "Unknown")
        if not vendor or "locally administered" in vendor.lower():
            vendor = "Unknown"
            
        if len(vendor) > 25:
            vendor = vendor[:25] 
            
        console.print(f"    • {config['target_ip']:<{max_ip_len}}  ·  {vendor}")
        
    console.print()
    
    answer = qselect(
        "What do you want to do?",
        choices=[
            questionary.Choice("Resume session",    value="use_saved"),
            questionary.Choice("Start new session", value="new_scan"),
            questionary.Choice("Rescan network",    value="rescan"),
            questionary.Choice("Exit",              value="exit"),
        ],
    )
 
    if answer is None:
        sys.stdout.write("\033[A\033[2K" * 3)
        sys.stdout.flush()
        console.print(" [error]Cancelled.[/error]")
        sys.exit(0)

    if answer == "exit":
        sys.exit(0)
 
    return answer


def prompt_operational_mode():
    """Ask user to select operational mode when starting a new session."""
    try:
        answer = qselect(
            "Select operational mode to begin:",
            [
                questionary.Choice("Blacklist Mode (Throttle only the specific devices you select)", value="blacklist"),
                questionary.Choice("Whitelist Mode (Throttle everyone except the safe devices you select)", value="whitelist")
            ],
            )

        if answer is None:
            sys.exit(0)
        
        return answer

    except KeyboardInterrupt:
        console.print("[bold red]✗[/bold red] Cancelled.")
        sys.exit(0)


def prompt_blacklist_selection(devices):
    choices = []
    for dev in devices:
        display_line = f"{dev['ip']:<15} · {dev['mac']:<19} · {dev['vendor'][:25]}"
        choices.append(
            questionary.Choice(title=display_line, value=dev)
        )
    
    try:
        answer = questionary.checkbox(
            "Select blacklist targets:",
            qmark="",
            instruction="(Space to select, Enter to confirm)",
            choices=choices,
            style=custom_style,
            pointer=">",
        ).ask()
        

        if not answer:
            console.print(" [bold red]✗ Cancelled.[/bold red] No devices selected.")
            sys.exit(0)
        
        return answer
    
    except KeyboardInterrupt:
        console.print("\n [bold red]✗ Cancelled.[/bold red]")
        sys.exit(0)


def prompt_whitelist_selection(devices):
    choices = []
    for dev in devices:
        display_line = f"{dev["ip"]:<15} · {dev["mac"]:<19} · {dev["vendor"]}"
        choices.append(
            questionary.Choice(title=display_line, value=dev)
        )
    
    try:
        answer = questionary.checkbox(
            "Select whitelist targets:",
            qmark="",
            instruction="(Space to select, Enter to confirm)",
            choices=choices,
            style=custom_style
        ).ask()

        if answer is None:
            sys.exit(0)
        
        return answer
    
    except KeyboardInterrupt:
        print("\n Cancelled.")
        sys.exit(0)


def prompt_session_review(interface, router_ip, mode, limit_mbps, targets):
    console.print()
    
    mode_str = mode.capitalize() if mode else "Blacklist"
    
    summary_text = (
        f"Operational Mode : {mode_str}\n"
        f"Interface        : {interface}\n"
        f"Router IP        : {router_ip}\n"
        f"Bandwidth Limit  : {limit_mbps} Mbps\n\n"
        f"Targets to Throttle ({len(targets)} devices):"
    )
    
    max_ip_len = max([len(tgt["ip"]) for tgt in targets]) if targets else 15
    
    target_lines = []
    for tgt in targets:
        vendor = tgt.get("vendor", "Unknown Vendor")
        
        if not vendor or "locally administered" in vendor.lower():
            vendor = "Unknown"
    
        if len(vendor) > 25:
            vendor = vendor[:25]
            
        mac = tgt.get("mac", "Unknown")
        
        target_lines.append(f"• [white]{tgt['ip']:<{max_ip_len}}  {mac:<17}  {vendor}[/white]")
    
    content_group = Group(
        summary_text,
        *target_lines
    )
    
    console.print(
        Panel(
            content_group,
            title="[bold white]CONFIGURATION REVIEW[/bold white]",
            title_align="left",
            padding=(1, 2),
            expand=False
        )
    )

    try:
        confirm = questionary.confirm(
            "Do you want to start the throttling session?",
            default=True,
            style=custom_style,
            qmark=""
        ).ask()
        
        if confirm is None:
            sys.stdout.write("\033[A\033[2K" * 2) 
            sys.stdout.flush()
            console.print("  [red]✗[/red] Cancelled.")
            sys.exit(0)
        
        if not confirm:
            sys.stdout.write("\033[A\033[2K")
            sys.stdout.flush()
            console.print("  [red]✗[/red] Cancelled.")
            sys.exit(0)

        return confirm

    except KeyboardInterrupt:
        sys.stdout.write("\033[A\033[2K" * 2)
        sys.stdout.flush()
        console.print("  [red]✗[/red] Cancelled.")
        sys.exit(0)