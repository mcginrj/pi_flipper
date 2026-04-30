import RPi.GPIO as GPIO
import time
import os

import display as D
import battery as B
from modules import sdr, nfc_tools, ir, wifi


def splash_screen():
    D.show_message("Portable Multi-", [
        "Protocol IoT",
        "Analysis Tool",
        "",
        "Loading..."
    ], color="CYAN")
    time.sleep(2)


def about_device():
    D.show_message("About Device", [
        "Portable Multi-",
        "Protocol IoT Tool",
        "Pi Zero 2 W",
        "LCD: Waveshare",
        "NFC: PN532 UART",
        "IR: GPIO17/18",
        "SDR: RTL-SDR",
        "Press A"
    ])
    D.wait_key()


def battery_info():
    D.show_message("Battery", [
        "Power: PiSugar S",
        "Battery: N/A",
        "Telemetry unavailable",
        "Press A"
    ])
    D.wait_key()


def system_info():
    import subprocess

    def cmd(command):
        try:
            return subprocess.getoutput(command).strip()
        except Exception:
            return "N/A"

    temp_raw = cmd("vcgencmd measure_temp")
    temp = temp_raw.replace("temp=", "") if temp_raw else "N/A"

    uptime = cmd("uptime -p").replace("up ", "")

    ip_list = cmd("hostname -I").split()
    ip = ip_list[0] if ip_list else "No IP"

    ssid = cmd("iwgetid -r")
    ssid = ssid if ssid else "Not connected"

    disk = cmd("df -h / | awk 'NR==2 {print $5 \" used\"}'")
    disk = disk if disk else "N/A"

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
    D.show_message("Shutdown", [
        "Hold B to confirm",
        "A to cancel"
    ], color="YELLOW")

    start = time.time()

    while time.time() - start < 3:
        if not GPIO.input(D.KEY_A):
            return

        if not GPIO.input(D.KEY_B) and time.time() - start > 1.5:
            D.show_message("Shutting down...", ["Goodbye!"])
            time.sleep(1)
            os.system("sudo shutdown -h now")
            return

        time.sleep(0.05)


MAIN_MENU = [
    ("[SDR] SDR Scanner", sdr.run),
    ("[NFC] NFC Reader", nfc_tools.run),
    ("[IR] IR Remote", ir.run),
    ("[WiFi] WiFi Scanner", wifi.run),
    ("[INFO] About Device", about_device),
    ("[BAT] Battery Info", battery_info),
    ("[SYS] System Info", system_info),
    ("[PWR] Shutdown", None),
]


def main():
    selected = 0

    splash_screen()

    while True:
        labels = [label for label, _ in MAIN_MENU]

        # Battery is intentionally -1 so display.py can show N/A or ignore it.
        bat = -1

        D.draw_screen("Pi Flipper", labels, selected, bat)

        key = D.wait_key()

        if key == "up":
            selected = (selected - 1) % len(MAIN_MENU)

        elif key == "down":
            selected = (selected + 1) % len(MAIN_MENU)

        elif key == "select":
            label, fn = MAIN_MENU[selected]

            if "Shutdown" in label:
                shutdown_confirm()

            elif fn:
                try:
                    fn()
                except Exception as e:
                    D.show_message("Error", [
                        str(e)[:30],
                        "Press A to go back"
                    ], color="RED")
                    D.wait_key()

        elif key == "shutdown":
            shutdown_confirm()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()
