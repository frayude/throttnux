# Throttnux

Ever had someone on your network hogging all the bandwidth with no way to control it? Throttnux lets you limit the internet speed of any device on your local network directly from your Linux machine, without touching the router, changing firmware, or needing admin access.

> **Linux only.** Windows and macOS are not supported. Throttnux relies on `arpspoof` and `tc`, which are Linux-exclusive tools with no equivalent on other operating systems.

Throttnux was inspired by Evillimiter and NetCut, which use similar ARP spoofing techniques.

## How It Works

1. **ARP Spoofing** Throttnux sends forged ARP replies to trick the target device into routing all its traffic through your machine.
2. **Traffic Shaping** Using Linux `tc` (HTB), the intercepted traffic is throttled to your specified limit before being forwarded to the router.

```
Without Throttnux:
Target Device ──────────────→ Router → Internet

With Throttnux:
Target Device → Your Machine (throttled) → Router → Internet
```

## Requirements

Linux only (tested on Arch Linux, CachyOS, Fedora 43+ and Ubuntu 26.04+)

## Installation

**1. Install Throttnux**
```bash
pipx install throttnux
```

**2. Run**
```bash
sudo ln -s ~/.local/bin/throttnux /usr/local/bin/throttnux
sudo throttnux
```

## Usage

Throttnux is fully interactive. No manual configuration needed. Once running, it will guide you through:

1. Selecting your network interface (auto-detected, skipped if only one)
2. Selecting your router/gateway (auto-detected, skipped if only one)
3. Picking the target device from a scanned list
4. Choosing a bandwidth limit
5. Confirming before proceeding
6. Auto-verifying whether throttling is active
7. Displaying a realtime bandwidth monitor

## Example Session

```
Welcome to Throttnux
Per-device bandwidth limiter via ARP spoofing

  Auto-selected interface: wlan0 (10.0.0.5)
  Auto-selected gateway: 10.0.0.1

  Devices detected on the network:
  No    IP          MAC                  Vendor
  ─────────────────────────────────────────────────────
  1     10.0.0.10   aa:bb:cc:dd:ee:01    Unknown
  2     10.0.0.11   aa:bb:cc:dd:ee:02    Samsung
  3     10.0.0.12   aa:bb:cc:dd:ee:03    Unknown

  Select device number to throttle: 2

  Select bandwidth limit:
  [1] 1 Mbps  -- heavy buffering, no HD YouTube
  [2] 2 Mbps  -- stuck at 480p
  [3] 3 Mbps  -- occasional buffering at 720p
  [4] Custom

  Choice (1-4): 1

  Target    : 10.0.0.11 (aa:bb:cc:dd:ee:02)
  Vendor    : Samsung
  Limit     : 1.0 Mbps
  Interface : wlan0
  Router    : 10.0.0.1

  Proceed? (y/n): y

[INFO] ARP spoofing active -> traffic from 10.0.0.11 routed through this machine
[INFO] Spoofing SUCCESSFUL -- 3241 packets captured from target
[INFO] Running. Press Ctrl+C to stop and restore target connection.

[LIVE ●] 10.0.0.11 -> 0.87 Mbps / 1.0 Mbps limit | 4.2 MB throttled | Uptime: 00:02:34
```

The `[LIVE]` line updates in-place every second. Status indicators:

`●` throttling active, target is being limited

`○` idle or spoofing not yet effective

## Stopping

Press `Ctrl+C` at any time. Throttnux will automatically stop ARP spoofing, remove all traffic shaping rules, restore the target device's full connection, and disable IP forwarding.

An emergency cleanup also runs if the script exits unexpectedly.

## Limitations

**The host machine must remain on and connected** for throttling to stay active. This is a fundamental limitation of ARP spoofing. ARP tables refresh periodically, so the spoofing process must run continuously.

If you need a persistent solution without keeping a machine on, consider a router that supports OpenWrt or DD-WRT with built-in QoS per device, or a low-power dedicated device such as a Raspberry Pi Zero.

## Disclaimer

This tool is intended for use on networks you own or have explicit permission to manage. Do not use it on networks you do not control.