# modules/wifi.py
import subprocess, display as D, RPi.GPIO as GPIO, time

def run():
    D.show_message("WiFi Scanner", ["Scanning nearby networks...", "Please wait..."])

    try:
        # Scan for nearby networks
        raw = subprocess.check_output(
            ["sudo", "iwlist", "wlan0", "scan"],
            stderr=subprocess.DEVNULL, text=True
        )
        networks = parse_scan(raw)

        if not networks:
            D.show_message("WiFi Scanner", ["No networks found", "Press A to go back"])
            D.wait_key()
            return

        # Display scrollable results
        sel    = 0
        page   = 0
        per_pg = 6

        while True:
            start  = page * per_pg
            page_nets = networks[start:start+per_pg]
            labels = [f"{n['signal']:>4}dBm {n['ssid'][:22]}" for n in page_nets]
            D.draw_screen(f"Networks ({len(networks)})", labels, sel % per_pg)
            key = D.wait_key()

            if key == 'up':
                sel = max(0, sel - 1)
                page = sel // per_pg
            elif key == 'down':
                sel = min(len(networks)-1, sel+1)
                page = sel // per_pg
            elif key == 'back':
                return
            elif key == 'select':
                n = networks[sel]
                D.show_message("Network Detail", [
                    f"SSID: {n['ssid'][:22]}",
                    f"MAC:  {n['mac']}",
                    f"Ch:   {n['channel']}",
                    f"Sig:  {n['signal']} dBm",
                    f"Enc:  {n['encryption']}",
                    "",
                    "A to go back"
                ])
                D.wait_key()

    except Exception as e:
        D.show_message("Error", [str(e)[:30], "Press A to go back"], color="RED")
        D.wait_key()

def parse_scan(raw):
    networks = []
    current  = {}
    for line in raw.split('\n'):
        line = line.strip()
        if 'Cell' in line and 'Address:' in line:
            if current: networks.append(current)
            current = {'mac': line.split('Address: ')[-1].strip(),
                       'ssid':'?','signal':0,'channel':0,'encryption':'?'}
        elif 'ESSID:' in line:
            current['ssid'] = line.split('"')[1] if '"' in line else 'Hidden'
        elif 'Signal level' in line:
            try:
                sig = line.split('Signal level=')[-1].split(' ')[0]
                current['signal'] = int(sig.replace('dBm',''))
            except Exception:
                pass
        elif 'Channel:' in line:
            try: current['channel'] = int(line.split('Channel:')[-1])
            except: pass
        elif 'Encryption key:' in line:
            current['encryption'] = 'WPA' if 'on' in line else 'Open'
    if current: networks.append(current)
    return sorted(networks, key=lambda x: x['signal'], reverse=True)
