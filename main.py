import RPi.GPIO as GPIO, time, os, sys
import display as D
import battery as B
from modules import sdr, nfc, ir, wifi

MAIN_MENU = [
    ("📡  SDR Scanner",     sdr.run),
    ("💳  NFC Reader",      nfc.run),
    ("🔴  IR Remote",       ir.run),
    ("📶  WiFi Scanner",    wifi.run),
    ("🔋  Battery Info",    None),
    ("⚙️  System Info",    None),
    ("🔴  Shutdown",        None),
]

def system_info():
    import subprocess
    import time
    import os

    def cmd(command):
        try:
            return subprocess.getoutput(command).strip()
        except Exception:
            return "N/A"

    # CPU temperature
    temp_raw = cmd("vcgencmd measure_temp")
    temp = temp_raw.replace("temp=", "") if temp_raw else "N/A"

    # Uptime
    uptime = cmd("uptime -p").replace("up ", "")

    # IP address
    ip = cmd("hostname -I").split()
    ip = ip[0] if ip else "No IP"

    # Connected SSID
    ssid = cmd("iwgetid -r")
    ssid = ssid if ssid else "Not connected"

    # Disk usage
    disk = cmd("df -h / | awk 'NR==2 {print $5 \" used\"}'")
    disk = disk if disk else "N/A"

    # Memory usage
    mem = cmd("free -h | awk '/Mem:/ {print $3 \"/\" $2}'")
    mem = mem if mem else "N/A"

    D.show_message("System Info", [
        f"Temp: {temp}",
        f"Uptime: {uptime[:18]}",
        f"IP: {ip}",
        f"SSID: {ssid[:18]}",
        f"Disk: {disk}",
        f"RAM: {mem}",
        "Power: PiSugar S",
        "Battery: N/A",
        "Press A"
    ])

    D.wait_key()

def shutdown_confirm():
    D.show_message("Shutdown", ["Hold B to confirm", "A to cancel"], color="YELLOW")
    t = time.time()
    while time.time() - t < 3:
        if not GPIO.input(D.KEY_A): return
        if not GPIO.input(D.KEY_B) and time.time() - t > 1.5:
            D.show_message("Shutting down...", ["Goodbye!"])
            time.sleep(1)
            os.system("sudo shutdown -h now")
            return
        time.sleep(0.05)

def main():
    selected = 0
    while True:
        bat = B.get_battery()
        labels = [label for label, _ in MAIN_MENU]
        D.draw_screen("Pi Flipper", labels, selected, bat)

        key = D.wait_key()

        if key == 'up':
            selected = (selected - 1) % len(MAIN_MENU)
        elif key == 'down':
            selected = (selected + 1) % len(MAIN_MENU)
        elif key == 'select':
            label, fn = MAIN_MENU[selected]
            if label.endswith("Battery Info"):
                bat = B.get_battery()
                D.show_message("Battery", [f"{bat}%", "Press A to go back"])
                D.wait_key()
            elif label.endswith("System Info"):
                system_info()
            elif label.endswith("Shutdown"):
                shutdown_confirm()
            elif fn:
                try:
                    fn()  # launch the module
                except Exception as e:
                    D.show_message("Error", [str(e)[:30], "Press A to go back"], color="RED")
                    D.wait_key()
        elif key == 'shutdown':
            shutdown_confirm()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()
