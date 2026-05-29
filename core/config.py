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
    
    saved_targets = config.get("targets", [])
    if not saved_targets and "target_ip" in config:
        saved_targets = [{
            "ip": config.get("target_ip"),
            "mac": config.get("target_mac", ""),
            "vendor": config.get("target_vendor", "")
        }]
    
    matched = []
    for saved in saved_targets:
        saved_mac = saved.get("mac", "").lower()
        saved_ip = saved.get("ip")
        
        for d in devices:
            if saved_mac and d["mac"].lower() == saved_mac:
                matched.append(d)
                break
            elif not saved_mac and d["ip"] == saved_ip:
                matched.append(d)
                break
                
    return matched if matched else None
    
    
def prompt_use_saved_config(config, matched_devices):
    """Ask user if they want to use the saved config."""
    mode_str = config.get("operational_mode", "Blacklist").capitalize()
    limit = config.get("limit_mbps", 1.0)
    
    console.print(f" [text]Last session : {mode_str} - {limit} Mbps[/text]")
    
   
    if matched_devices:
        max_ip_len = max([len(d["ip"]) for d in matched_devices])
        for dev in matched_devices:
            vendor = dev.get("vendor", "Unknown")
            if not vendor or "locally administered" in vendor.lower():
                vendor = "Unknown"
            
            if len(vendor) > 25:
                vendor = vendor[:25]
            
            console.print(f"   [text]{dev['ip']:<{max_ip_len}}  • {vendor}[/text]")
        
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
            console.print(" [error]Cancelled.[/error]")
            sys.exit(0)
        
        return answer

    except KeyboardInterrupt:
        console.print(" [error]Cancelled.[/error]")
        sys.exit(0)


def prompt_blacklist_selection(devices, default_targets=None):
    if default_targets is None:
        default_targets = []
        
    default_macs = [t.get("mac", "").lower() for t in default_targets]
    
    choices = []
    initial_focus = None
    
    for dev in devices:
        display_line = f"{dev['ip']:<15} · {dev['mac']:<19} · {dev['vendor'][:25]}"
        is_checked = dev["mac"].lower() in default_macs
        
        choice = questionary.Choice(title=display_line, value=dev, checked=is_checked)
        choices.append(choice)
        
        if is_checked and initial_focus is None:
            initial_focus = choice

    if initial_focus is None and choices:
        initial_focus = choices[0]
    
    try:
        answer = questionary.checkbox(
            "Select blacklist targets:",
            qmark="",
            instruction="(Space to select, Enter to confirm)",
            choices=choices,
            initial_choice=initial_focus,
            style=custom_style,
            pointer=">",
        ).ask()
        
        if not answer:
            console.print(" [error]Cancelled. No devices selected.[/error]")
            sys.exit(0)
        
        return answer
    
    except KeyboardInterrupt:
        console.print("\n [error]Cancelled.[/error]")
        sys.exit(0)


def prompt_whitelist_selection(devices, default_targets=None):
    if default_targets is None:
        default_targets = []
        
    default_macs = [t.get("mac", "").lower() for t in default_targets]
    
    choices = []
    initial_focus = None
    
    for dev in devices:
        display_line = f"{dev['ip']:<15} · {dev['mac']:<19} · {dev['vendor']}"
        is_checked = dev["mac"].lower() in default_macs
        
        choice = questionary.Choice(title=display_line, value=dev, checked=is_checked)
        choices.append(choice)
        
        if is_checked and initial_focus is None:
            initial_focus = choice

    if initial_focus is None and choices:
        initial_focus = choices[0]
    
    try:
        answer = questionary.checkbox(
            "Select whitelist targets:",
            qmark="",
            instruction="(Space to select, Enter to confirm)",
            choices=choices,
            initial_choice=initial_focus,
            style=custom_style
        ).ask()

        if not answer:
            console.print(" bold red]✗ Cancelled.[/bold red] No devices selected.")
            sys.exit(0)
        
        return answer
    
    except KeyboardInterrupt:
        console.print("\n [bold red]✗ Cancelled.[/bold red]")
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