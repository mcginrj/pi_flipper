import subprocess
import time
import json
import os
import display as D

BANDS = [
    ("315 MHz", "315000000"),
    ("433 MHz", "433920000"),
    ("868 MHz", "868000000"),
    ("915 MHz", "915000000"),
]

LOG_DIR = os.path.expanduser("~/pi_flipper/logs")
LOG_FILE = os.path.join(LOG_DIR, "sdr_hits.json")


def wait_back():
    while True:
        key = D.wait_key()
        if key in ["back", "select", "shutdown"]:
            return


def scan_rtl433(label, freq, duration=30):
    import select
    import RPi.GPIO as GPIO

    D.show_message("SDR Scan", [
        f"Band: {label}",
        "A = stop",
        "Listening..."
    ])

    cmd = [
        "rtl_433",
        "-f", freq,
        "-R", "0",
        "-M", "newmodel",
        "-F", "json"
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1
    )

    hits = []
    deadline = time.time() + duration

    while time.time() < deadline:
        # A button = back button on your display.py
        if not GPIO.input(D.KEY_A):
            break

        ready, _, _ = select.select([proc.stdout], [], [], 0.1)

        if ready:
            line = proc.stdout.readline()

            if line:
                try:
                    data = json.loads(line)
                    model = str(data.get("model", "Unknown"))
                    ident = str(data.get("id", ""))
                    label_text = f"{model} {ident}".strip()

                    if label_text not in hits:
                        hits.append(label_text[:35])
                except Exception:
                    pass

    proc.terminate()

    if hits:
        save_hits(label, freq, hits)
        show_hits(label, hits)
    else:
        D.show_message("SDR", [
            f"No hits on {label}",
            "Press A"
        ])
        wait_back()

def show_hits(title, hits):
    selected = 0

    while True:
        D.draw_screen(title, hits[:8], selected if selected < 8 else 7)
        key = D.wait_key()

        if key == "up":
            selected = (selected - 1) % len(hits)
        elif key == "down":
            selected = (selected + 1) % len(hits)
        elif key in ["back", "select", "shutdown"]:
            return


def save_hits(label, freq, hits):
    os.makedirs(LOG_DIR, exist_ok=True)

    entry = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "band": label,
        "freq": freq,
        "hits": hits
    }

    old = []
    if os.path.exists(LOG_FILE):
        try:
            import json
            with open(LOG_FILE, "r") as f:
                old = json.load(f)
        except Exception:
            old = []

    old.append(entry)

    with open(LOG_FILE, "w") as f:
        json.dump(old, f, indent=2)


def rtl_test_screen():
    D.show_message("SDR Test", ["Running rtl_test...", "Please wait"])

    try:
        out = subprocess.getoutput("rtl_test -t")
        lines = []

        for line in out.splitlines():
            if "Found" in line or "NooElec" in line or "Realtek" in line or "Rafael" in line:
                lines.append(line[:24])

        if not lines:
            lines = ["No useful output"]

        lines.append("Press A")
        D.show_message("RTL Test", lines[:8])
    except Exception as e:
        D.show_message("RTL Error", [str(e)[:28], "Press A"], color="RED")

    wait_back()


def fm_power_test():
    D.show_message("FM Test", [
        "Scanning FM band",
        "88-108 MHz...",
        "Please wait"
    ])

    try:
        subprocess.getoutput("rm -f /tmp/fm_scan.csv")
        subprocess.getoutput("rtl_power -f 88M:108M:200k -i 1 -e 10s /tmp/fm_scan.csv")
        out = subprocess.getoutput("tail -3 /tmp/fm_scan.csv")

        if out.strip():
            D.show_message("FM Test", [
                "FM scan complete",
                "SDR is working",
                "Press A"
            ], color="GREEN")
        else:
            D.show_message("FM Test", [
                "No FM data file",
                "Check antenna",
                "Press A"
            ], color="RED")
    except Exception as e:
        D.show_message("FM Error", [str(e)[:28], "Press A"], color="RED")

    wait_back()


def run():
    menu = [
        "RTL Device Test",
        "FM Power Test",
        "Scan 315 MHz",
        "Scan 433 MHz",
        "Scan 868 MHz",
        "Scan 915 MHz",
        "Back",
    ]

    selected = 0

    while True:
        D.draw_screen("SDR Tools", menu, selected)
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

            elif choice.startswith("Scan"):
                for label, freq in BANDS:
                    if label in choice:
                        scan_rtl433(label, freq)
                        break

            elif choice == "Back":
                return
