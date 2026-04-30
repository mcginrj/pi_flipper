import subprocess
import re
import time
import json
import os
import display as D

LOG_DIR = os.path.expanduser("~/pi_flipper/logs")
LOG_FILE = os.path.join(LOG_DIR, "wifi_scans.json")


def run_cmd(cmd):
    try:
        return subprocess.getoutput(cmd)
    except Exception:
        return ""


def wait_back():
    while True:
        key = D.wait_key()
        if key in ["back", "select", "shutdown"]:
            return key


def signal_rating_percent(signal):
    try:
        s = int(signal)
        if s >= 80:
            return "Excellent"
        if s >= 60:
            return "Good"
        if s >= 40:
            return "Fair"
        return "Weak"
    except Exception:
        return "?"


def signal_rating_dbm(signal):
    try:
        s = int(float(signal))
        if s >= -50:
            return "Excellent"
        if s >= -65:
            return "Good"
        if s >= -75:
            return "Fair"
        return "Weak"
    except Exception:
        return "?"


def freq_to_channel(freq):
    try:
        f = int(freq)
        if f == 2484:
            return 14
        if 2412 <= f <= 2472:
            return int((f - 2407) / 5)
        if 5000 <= f <= 5900:
            return int((f - 5000) / 5)
    except Exception:
        pass
    return 0


def freq_to_band(freq):
    try:
        f = int(freq)
        if f < 3000:
            return "2.4GHz"
        if f < 7000:
            return "5GHz"
        return "6GHz"
    except Exception:
        return "?"


def channel_to_band(channel):
    try:
        ch = int(channel)
        if 1 <= ch <= 14:
            return "2.4GHz"
        if ch >= 32:
            return "5GHz"
    except Exception:
        pass
    return "?"


def parse_security_iw(block):
    text = "\n".join(block)

    if "capability:" in text and "Privacy" not in text:
        return "Open"

    if "SAE" in text:
        return "WPA3"

    if "RSN:" in text:
        return "WPA2"

    if "WPA:" in text:
        return "WPA"

    if "Privacy" in text:
        return "WEP/Unknown"

    return "Unknown"


def parse_nmcli_multiline(raw):
    
    networks = []
    current = {}

    for line in raw.splitlines():
        line = line.rstrip()

        if not line.strip():
            if current:
                networks.append(current)
                current = {}
            continue

        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip().upper()
        value = value.strip()

        if key == "SSID" and current:
            networks.append(current)
            current = {}

        if key == "SSID":
            current["ssid"] = value if value else "Hidden"
        elif key == "BSSID":
            current["mac"] = value
        elif key == "CHAN":
            current["channel"] = value
        elif key == "SIGNAL":
            current["signal"] = value
        elif key == "SECURITY":
            current["security"] = value if value else "Open"

    if current:
        networks.append(current)

    clean = []
    seen = set()

    for n in networks:
        ssid = n.get("ssid", "Hidden")
        mac = n.get("mac", "?")
        channel = n.get("channel", "?")
        signal_raw = n.get("signal", "0")
        security = n.get("security", "Unknown")

        try:
            signal = int(signal_raw)
        except Exception:
            signal = 0

        key = mac if mac != "?" else ssid + channel

        if key in seen:
            continue

        seen.add(key)

        clean.append({
            "ssid": ssid,
            "mac": mac,
            "signal": signal,
            "signal_unit": "%",
            "quality": signal_rating_percent(signal),
            "freq": 0,
            "channel": channel,
            "band": channel_to_band(channel),
            "security": security,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return sorted(clean, key=lambda x: x["signal"], reverse=True)


def parse_iw_network_block(mac, block):
    ssid = "Hidden"
    signal = -999
    freq = 0

    for line in block:
        line = line.strip()

        if line.startswith("SSID:"):
            val = line.replace("SSID:", "", 1).strip()
            ssid = val if val else "Hidden"

        elif line.startswith("signal:"):
            m = re.search(r"signal:\s*(-?\d+\.?\d*)", line)
            if m:
                signal = int(float(m.group(1)))

        elif line.startswith("freq:"):
            m = re.search(r"freq:\s*(\d+)", line)
            if m:
                freq = int(m.group(1))

    return {
        "ssid": ssid,
        "mac": mac,
        "signal": signal,
        "signal_unit": "dBm",
        "quality": signal_rating_dbm(signal),
        "freq": freq,
        "channel": freq_to_channel(freq),
        "band": freq_to_band(freq),
        "security": parse_security_iw(block),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def parse_iw_scan(raw):
    networks = []
    current = []
    mac = None

    for line in raw.splitlines():
        line = line.rstrip()

        if line.startswith("BSS "):
            if current and mac:
                networks.append(parse_iw_network_block(mac, current))

            current = [line]
            parts = line.split()
            mac = parts[1] if len(parts) > 1 else "?"
        else:
            if current is not None:
                current.append(line)

    if current and mac:
        networks.append(parse_iw_network_block(mac, current))

    clean = []
    seen = set()

    for n in networks:
        key = n["mac"]
        if key not in seen:
            clean.append(n)
            seen.add(key)

    return sorted(clean, key=lambda x: x["signal"], reverse=True)


def scan_networks():
    D.show_message("WiFi", ["Scanning...", "Please wait"])

    run_cmd("nmcli dev wifi rescan")

    raw = run_cmd("nmcli -m multiline -f SSID,BSSID,CHAN,SIGNAL,SECURITY dev wifi list")

    networks = parse_nmcli_multiline(raw)

    if networks:
        return networks

    raw = run_cmd("sudo iw dev wlan0 scan")
    networks = parse_iw_scan(raw)

    return networks


def show_network_detail(n):
    signal_unit = n.get("signal_unit", "%")
    signal = n.get("signal", "?")

    D.show_message("WiFi Detail", [
        f"SSID: {str(n.get('ssid', 'Hidden'))[:20]}",
        f"Sig: {signal}{signal_unit}",
        f"Rate: {n.get('quality', '?')}",
        f"Ch: {n.get('channel', '?')} {n.get('band', '?')}",
        f"Sec: {str(n.get('security', '?'))[:20]}",
        f"MAC: {str(n.get('mac', '?'))[:17]}",
        "Press A"
    ])
    wait_back()


def connected_info():
    link = run_cmd("iw dev wlan0 link")
    ip = run_cmd("hostname -I").strip()
    route = run_cmd("ip route | grep default")

    ssid = run_cmd("iwgetid -r").strip()
    if not ssid:
        ssid = "Not connected"

    signal = "?"

    for line in link.splitlines():
        line = line.strip()
        if line.startswith("signal:"):
            signal = line.replace("signal:", "").strip()

    gateway = "?"

    if route:
        parts = route.split()
        if "via" in parts:
            gateway = parts[parts.index("via") + 1]

    D.show_message("Connected", [
        f"SSID: {ssid[:20]}",
        f"IP: {ip[:22] if ip else 'None'}",
        f"Gateway: {gateway}",
        f"Signal: {signal}",
        "Press A"
    ])
    wait_back()


def channel_summary(networks):
    if not networks:
        D.show_message("Channels", ["No scan data", "Run scan first", "Press A"])
        wait_back()
        return

    counts = {}

    for n in networks:
        ch = str(n.get("channel", "?"))
        if ch and ch != "?":
            counts[ch] = counts.get(ch, 0) + 1

    if not counts:
        D.show_message("Channels", ["No channels found", "Press A"])
        wait_back()
        return

    def sort_key(item):
        try:
            return int(item[0])
        except Exception:
            return 999

    items = sorted(counts.items(), key=sort_key)

    lines = [f"Ch {ch}: {count} nets" for ch, count in items[:7]]

    best = min(items, key=lambda x: x[1])
    lines.append(f"Best: Ch {best[0]}")
    lines.append("Press A")

    D.show_message("Channels", lines[:9])
    wait_back()


def save_scan(networks):
    os.makedirs(LOG_DIR, exist_ok=True)

    entry = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(networks),
        "networks": networks,
    }

    old = []

    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                old = json.load(f)
        except Exception:
            old = []

    old.append(entry)

    with open(LOG_FILE, "w") as f:
        json.dump(old, f, indent=2)

    D.show_message("Saved", [
        f"{len(networks)} networks",
        "Saved to logs/",
        "wifi_scans.json",
        "Press A"
    ])
    wait_back()


def network_list(networks):
    if not networks:
        D.show_message("WiFi", ["No networks found", "Press A"])
        wait_back()
        return

    selected = 0
    per_page = 6

    while True:
        start = (selected // per_page) * per_page
        end = start + per_page
        visible = networks[start:end]

        page = (selected // per_page) + 1
        total_pages = ((len(networks) - 1) // per_page) + 1

        labels = []

        for n in visible:
            ssid = str(n.get("ssid", "Hidden"))[:10]
            signal = n.get("signal", "?")
            unit = n.get("signal_unit", "%")
            ch = n.get("channel", "?")

            labels.append(f"{ssid} {signal}{unit} Ch{ch}")

        D.draw_screen(f"Networks {page}/{total_pages}", labels, selected - start)

        key = D.wait_key()

        if key == "up":
            selected = (selected - 1) % len(networks)

        elif key == "down":
            selected = (selected + 1) % len(networks)

        elif key == "select":
            show_network_detail(networks[selected])

        elif key in ["back", "shutdown"]:
            return


def run():
    networks = []

    menu = [
        "Scan Networks",
        "Connected Info",
        "Channel Summary",
        "Save Last Scan",
        "Back",
    ]

    selected = 0

    while True:
        D.draw_screen("WiFi Scanner", menu, selected)

        key = D.wait_key()

        if key == "up":
            selected = (selected - 1) % len(menu)

        elif key == "down":
            selected = (selected + 1) % len(menu)

        elif key == "back":
            return

        elif key == "select":
            choice = menu[selected]

            if choice == "Scan Networks":
                try:
                    networks = scan_networks()
                    network_list(networks)
                except Exception as e:
                    D.show_message("WiFi Error", [str(e)[:28], "Press A"], color="RED")
                    wait_back()

            elif choice == "Connected Info":
                connected_info()

            elif choice == "Channel Summary":
                channel_summary(networks)

            elif choice == "Save Last Scan":
                save_scan(networks)

            elif choice == "Back":
                return

        elif key == "shutdown":
            return
