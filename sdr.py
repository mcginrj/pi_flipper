import subprocess
import time
import json
import os
import select
import re
import display as D

LOG_DIR = os.path.expanduser("~/pi_flipper/logs")
LOG_FILE = os.path.join(LOG_DIR, "sdr_hits.json")

BANDS = [
    ("315", "315M", "315000000"),
    ("433", "433.92M", "433920000"),
    ("868", "868M", "868000000"),
    ("915", "915M", "915000000"),
]


def wait_back():
    while True:
        key = D.wait_key()
        if key in ["back", "select", "shutdown"]:
            return


def stop_pressed():
    try:
        import RPi.GPIO as GPIO
        return not GPIO.input(D.KEY_A)
    except Exception:
        return False


def save_result(entry):
    os.makedirs(LOG_DIR, exist_ok=True)
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


def rtl_test_screen():
    D.show_message("SDR Test", ["Checking dongle...", "Please wait"])

    out = subprocess.getoutput("rtl_test -t")
    lines = []

    for line in out.splitlines():
        if "Found" in line or "NooElec" in line or "Realtek" in line or "Rafael" in line:
            lines.append(line[:24])

    if not lines:
        lines = ["No useful output"]

    lines.append("Press A")
    D.show_message("RTL Test", lines[:8])
    wait_back()


def fm_power_test():
    D.show_message("FM Test", ["Scanning FM band", "88-108 MHz..."])

    subprocess.getoutput("rm -f /tmp/fm_scan.csv")
    subprocess.getoutput("rtl_power -f 88M:108M:200k -i 1 -e 10s /tmp/fm_scan.csv")
    out = subprocess.getoutput("tail -1 /tmp/fm_scan.csv")

    if out.strip():
        D.show_message("FM Test", ["FM data found", "SDR working", "Press A"], color="GREEN")
    else:
        D.show_message("FM Test", ["No FM data", "Check antenna", "Press A"], color="RED")

    wait_back()


def decode_band(label, freq_json, duration=30):
    D.show_message(f"Decode {label}", ["Known devices", "A = stop", "Listening..."])

    proc = subprocess.Popen(
        ["rtl_433", "-f", freq_json, "-R", "0", "-M", "newmodel", "-F", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1
    )

    hits = []
    deadline = time.time() + duration

    while time.time() < deadline:
        if stop_pressed():
            break

        ready, _, _ = select.select([proc.stdout], [], [], 0.1)

        if ready:
            line = proc.stdout.readline()
            if line:
                try:
                    data = json.loads(line)
                    model = str(data.get("model", "Unknown"))
                    ident = str(data.get("id", ""))
                    channel = str(data.get("channel", ""))
                    battery = str(data.get("battery_ok", ""))

                    hit = f"{model} {ident}".strip()
                    if channel:
                        hit += f" Ch{channel}"
                    if battery:
                        hit += f" B:{battery}"

                    if hit not in hits:
                        hits.append(hit[:35])
                except Exception:
                    pass

    proc.terminate()

    save_result({
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": f"decode_{label}",
        "hits": hits
    })

    if hits:
        D.show_message(f"Decoded {label}", hits[:7] + ["Press A"], color="GREEN")
    else:
        D.show_message(f"Decode {label}", ["No known devices", "Try Analyze mode", "Press A"])

    wait_back()


def analyze_band(label, freq_a, duration=20):
    D.show_message(f"Analyze {label}", ["Raw RF detect", "A = stop", "Press remote"])

    proc = subprocess.Popen(
        ["rtl_433", "-f", freq_a, "-A"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    packets = 0
    rssi = "?"
    noise = "?"
    offset = "?"
    modulation = "Unknown"

    deadline = time.time() + duration

    while time.time() < deadline:
        if stop_pressed():
            break

        ready, _, _ = select.select([proc.stdout], [], [], 0.1)

        if ready:
            line = proc.stdout.readline()
            if not line:
                continue

            line = line.strip()

            if "Detected OOK package" in line or "Detected FSK package" in line:
                packets += 1

            if "RSSI:" in line:
                m = re.search(r"RSSI:\s*([-0-9.]+)", line)
                if m:
                    rssi = m.group(1) + " dB"

                m = re.search(r"Noise:\s*([-0-9.]+)", line)
                if m:
                    noise = m.group(1) + " dB"

            if "Frequency offsets" in line:
                offset = line.split(":")[-1].strip()[:18]

            if "Guessing modulation" in line:
                modulation = line.replace("Guessing modulation:", "").strip()[:18]

    proc.terminate()

    lines = [
        "RF Activity Found" if packets > 0 else "No RF bursts",
        f"Bursts: {packets}",
        f"RSSI: {rssi}",
        f"Noise: {noise}",
        f"Offset: {offset}",
        f"Mod: {modulation}",
        "Press A",
    ]

    save_result({
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": f"analyze_{label}",
        "bursts": packets,
        "rssi": rssi,
        "noise": noise,
        "offset": offset,
        "modulation": modulation
    })

    D.show_message(f"{label} Analysis", lines[:8], color="GREEN" if packets > 0 else "RED")
    wait_back()


def demo_scan_band(label, freq_a, freq_json):
    D.show_message(f"Demo {label}", ["Decode + raw", "A = stop", "Press remote"])

    decoded = []

    proc = subprocess.Popen(
        ["rtl_433", "-f", freq_json, "-R", "0", "-F", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1
    )

    deadline = time.time() + 10

    while time.time() < deadline:
        if stop_pressed():
            break

        ready, _, _ = select.select([proc.stdout], [], [], 0.1)

        if ready:
            line = proc.stdout.readline()
            if line:
                try:
                    data = json.loads(line)
                    model = str(data.get("model", "Unknown"))
                    if model not in decoded:
                        decoded.append(model[:20])
                except Exception:
                    pass

    proc.terminate()

    bursts = 0
    rssi = "?"

    proc = subprocess.Popen(
        ["rtl_433", "-f", freq_a, "-A"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    deadline = time.time() + 10

    while time.time() < deadline:
        if stop_pressed():
            break

        ready, _, _ = select.select([proc.stdout], [], [], 0.1)

        if ready:
            line = proc.stdout.readline()
            if not line:
                continue

            if "Detected OOK package" in line or "Detected FSK package" in line:
                bursts += 1

            if "RSSI:" in line:
                m = re.search(r"RSSI:\s*([-0-9.]+)", line)
                if m:
                    rssi = m.group(1) + " dB"

    proc.terminate()

    lines = [
        f"{label} MHz Results",
        f"Decoded: {len(decoded)}",
        f"Raw bursts: {bursts}",
        f"RSSI: {rssi}",
    ]

    if decoded:
        lines.append(decoded[0])
    elif bursts > 0:
        lines.append("Unknown RF device")
    else:
        lines.append("No activity found")

    lines.append("Press A")

    save_result({
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": f"demo_{label}",
        "decoded": decoded,
        "raw_bursts": bursts,
        "rssi": rssi
    })

    D.show_message(f"SDR Demo {label}", lines[:8], color="GREEN" if bursts or decoded else "RED")
    wait_back()


def view_saved():
    if not os.path.exists(LOG_FILE):
        D.show_message("SDR Logs", ["No logs yet", "Press A"])
        wait_back()
        return

    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        D.show_message("SDR Logs", ["Log read error", "Press A"])
        wait_back()
        return

    if not data:
        D.show_message("SDR Logs", ["No entries", "Press A"])
        wait_back()
        return

    last = data[-1]
    lines = [
        last.get("time", "")[11:19],
        f"Mode: {last.get('mode', '?')}",
    ]

    if "raw_bursts" in last:
        lines.append(f"Bursts: {last['raw_bursts']}")
    if "bursts" in last:
        lines.append(f"Bursts: {last['bursts']}")
    if "rssi" in last:
        lines.append(f"RSSI: {last['rssi']}")
    if "hits" in last:
        lines.append(f"Hits: {len(last['hits'])}")

    lines.append("Press A")
    D.show_message("Last SDR Log", lines[:8])
    wait_back()


def clear_logs():
    try:
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
        D.show_message("SDR Logs", ["Logs cleared", "Press A"], color="GREEN")
    except Exception as e:
        D.show_message("SDR Logs", [str(e)[:28], "Press A"], color="RED")

    wait_back()


def band_menu(label, freq_a, freq_json):
    menu = [
        f"Decode {label}",
        f"Analyze {label}",
        f"Demo Scan {label}",
        "Back",
    ]

    selected = 0

    while True:
        D.draw_screen(f"{label} MHz", menu, selected)
        key = D.wait_key()

        if key == "up":
            selected = (selected - 1) % len(menu)

        elif key == "down":
            selected = (selected + 1) % len(menu)

        elif key == "back":
            return

        elif key == "select":
            choice = menu[selected]

            if choice.startswith("Decode"):
                decode_band(label, freq_json)

            elif choice.startswith("Analyze"):
                analyze_band(label, freq_a)

            elif choice.startswith("Demo"):
                demo_scan_band(label, freq_a, freq_json)

            elif choice == "Back":
                return


def run():
    menu = [
        "RTL Device Test",
        "FM Power Test",
        "315 MHz Tools",
        "433 MHz Tools",
        "868 MHz Tools",
        "915 MHz Tools",
        "View Saved",
        "Clear Logs",
        "Back",
    ]

    selected = 0
    per_page = 7

    while True:
        start = (selected // per_page) * per_page
        visible = menu[start:start + per_page]

        D.draw_screen("SDR Tools", visible, selected - start)
        key = D.wait_key()

        if key == "up":
            selected = (selected - 1) % len(menu)

        elif key == "down":
            selected = (selected + 1) % len(menu)

        elif key == "back":
            return

        elif key == "select":
            choice = menu[selected]

            if choice == "RTL Device Test":
                rtl_test_screen()

            elif choice == "FM Power Test":
                fm_power_test()

            elif choice.endswith("MHz Tools"):
                band = choice.split()[0]
                for label, freq_a, freq_json in BANDS:
                    if label == band:
                        band_menu(label, freq_a, freq_json)
                        break

            elif choice == "View Saved":
                view_saved()

            elif choice == "Clear Logs":
                clear_logs()

            elif choice == "Back":
                return
