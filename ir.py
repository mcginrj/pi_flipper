# modules/ir.py
import os
import json
import time
import math
import subprocess

import RPi.GPIO as GPIO
import pigpio
import display as D

IR_RX = 17
IR_TX = 18

DB = os.path.expanduser("~/pi_flipper/data/ir_codes.json")
CARRIER_HZ = 38000
DUTY_CYCLE = 0.33

MIN_PULSES_TO_SAVE = 12
MAX_CAPTURE_SECONDS = 6
CAPTURE_END_GAP_SECONDS = 0.15


def ensure_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.exists(DB):
        with open(DB, "w") as f:
            json.dump({}, f, indent=2)


def load_db():
    ensure_db()
    try:
        with open(DB, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_db(db):
    ensure_db()
    with open(DB, "w") as f:
        json.dump(db, f, indent=2)


def wait_back():
    while True:
        key = D.wait_key()
        if key in ["back", "select", "shutdown"]:
            return key


def show_error(title, err):
    D.show_message(title, [str(err)[:28], "Press A"], color="RED")
    wait_back()


def pigpio_ready():
    pi = pigpio.pi()
    if not pi.connected:
        return None
    return pi


def start_pigpio_if_needed():
    pi = pigpio_ready()
    if pi:
        pi.stop()
        return True

    try:
        subprocess.run(["sudo", "systemctl", "start", "pigpiod"], timeout=5)
        time.sleep(0.5)
    except Exception:
        pass

    pi = pigpio_ready()
    if pi:
        pi.stop()
        return True

    return False


def normalize_pulses(pulses):
    clean = []

    for item in pulses:
        if len(item) != 2:
            continue

        state = int(item[0])
        dur = int(item[1])

        # Skip tiny noise
        if dur < 80:
            continue

        # Cap weird long gaps
        if dur > 200000:
            dur = 200000

        clean.append([state, dur])

    return clean


def total_duration_ms(pulses):
    return int(sum(int(p[1]) for p in pulses) / 1000)


def next_code_name(db):
    i = 1
    while f"code_{i}" in db:
        i += 1
    return f"code_{i}"


def capture_pulses():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(IR_RX, GPIO.IN)

    pulses = []
    last_state = GPIO.input(IR_RX)
    last_time = time.time()

    start_time = time.time()
    deadline = start_time + MAX_CAPTURE_SECONDS
    saw_signal = False

    while time.time() < deadline:
        state = GPIO.input(IR_RX)

        if state != last_state:
            now = time.time()
            duration = int((now - last_time) * 1_000_000)

            pulses.append([int(last_state), duration])

            last_state = state
            last_time = now
            saw_signal = True

        if saw_signal and (time.time() - last_time) > CAPTURE_END_GAP_SECONDS:
            break

        time.sleep(0.00005)

    return normalize_pulses(pulses)


def learn_code():
    db = load_db()

    D.show_message("Learning IR", [
        "Point remote",
        "at receiver",
        "Press button"
    ])

    try:
        pulses = capture_pulses()
    except Exception as e:
        show_error("Learn Error", e)
        return

    if len(pulses) < MIN_PULSES_TO_SAVE:
        D.show_message("Learn Failed", [
            "Weak/no signal",
            f"Pulses: {len(pulses)}",
            "Press A"
        ], color="RED")
        wait_back()
        return

    name = next_code_name(db)

    db[name] = {
        "name": name,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "carrier_hz": CARRIER_HZ,
        "pulses": pulses,
        "pulse_count": len(pulses),
        "duration_ms": total_duration_ms(pulses),
    }

    save_db(db)

    D.show_message("Saved IR", [
        f"Name: {name}",
        f"Pulses: {len(pulses)}",
        f"Len: {total_duration_ms(pulses)}ms",
        "Press A"
    ], color="GREEN")
    wait_back()


def carrier_wave_pulses(gpio, duration_us):
    """
    Create pigpio pulses for a 38kHz carrier during one IR mark.
    """
    period = int(1_000_000 / CARRIER_HZ)
    on_time = max(1, int(period * DUTY_CYCLE))
    off_time = max(1, period - on_time)

    pulses = []
    cycles = max(1, int(duration_us / period))

    for _ in range(cycles):
        pulses.append(pigpio.pulse(1 << gpio, 0, on_time))
        pulses.append(pigpio.pulse(0, 1 << gpio, off_time))

    return pulses


def build_wave_from_code(code):
    raw = code.get("pulses", code if isinstance(code, list) else [])
    pulses = normalize_pulses(raw)

    wave = []

    for state, dur in pulses:
        # VS1838B output is usually active-low:
        # state 0 means IR carrier was present from the remote.
        if int(state) == 0:
            wave.extend(carrier_wave_pulses(IR_TX, int(dur)))
        else:
            wave.append(pigpio.pulse(0, 1 << IR_TX, int(dur)))

    return wave


def transmit_code(name, repeat=1):
    db = load_db()

    if name not in db:
        D.show_message("IR Error", ["Code not found", "Press A"], color="RED")
        wait_back()
        return

    if not start_pigpio_if_needed():
        D.show_message("pigpio Error", [
            "pigpiod not running",
            "sudo systemctl",
            "start pigpiod"
        ], color="RED")
        wait_back()
        return

    pi = pigpio.pi()

    try:
        pi.set_mode(IR_TX, pigpio.OUTPUT)
        pi.write(IR_TX, 0)

        wave = build_wave_from_code(db[name])

        if not wave:
            D.show_message("IR Error", ["No pulse data", "Press A"], color="RED")
            wait_back()
            return

        pi.wave_clear()
        pi.wave_add_generic(wave)
        wid = pi.wave_create()

        if wid < 0:
            D.show_message("IR Error", ["Wave create failed", "Press A"], color="RED")
            wait_back()
            return

        for _ in range(repeat):
            pi.wave_send_once(wid)
            while pi.wave_tx_busy():
                time.sleep(0.001)
            time.sleep(0.08)

        pi.wave_delete(wid)

        D.show_message("IR Sent", [
            f"Sent: {name[:18]}",
            f"Repeat: {repeat}",
            "Press A"
        ], color="GREEN")
        wait_back()

    except Exception as e:
        show_error("Send Error", e)

    finally:
        try:
            pi.write(IR_TX, 0)
            pi.stop()
        except Exception:
            pass


def send_menu(name):
    menu = [
        "Send Once",
        "Send 3 Times",
        "Delete Code",
        "Back",
    ]

    selected = 0

    while True:
        D.draw_screen(name[:18], menu, selected)
        key = D.wait_key()

        if key == "up":
            selected = (selected - 1) % len(menu)

        elif key == "down":
            selected = (selected + 1) % len(menu)

        elif key == "back":
            return

        elif key == "select":
            choice = menu[selected]

            if choice == "Send Once":
                transmit_code(name, repeat=1)

            elif choice == "Send 3 Times":
                transmit_code(name, repeat=3)

            elif choice == "Delete Code":
                delete_code(name)
                return

            elif choice == "Back":
                return


def delete_code(name):
    db = load_db()

    if name in db:
        del db[name]
        save_db(db)
        D.show_message("Deleted", [name[:20], "Press A"], color="GREEN")
    else:
        D.show_message("Delete", ["Code not found", "Press A"], color="RED")

    wait_back()


def test_ir_led():
    if not start_pigpio_if_needed():
        D.show_message("pigpio Error", [
            "pigpiod not running",
            "Press A"
        ], color="RED")
        wait_back()
        return

    D.show_message("IR LED Test", [
        "Use phone camera",
        "Look for blinking",
        "Testing..."
    ])

    pi = pigpio.pi()

    try:
        pi.set_mode(IR_TX, pigpio.OUTPUT)
        pi.write(IR_TX, 0)

        # 10 short carrier bursts
        wave = []
        for _ in range(10):
            wave.extend(carrier_wave_pulses(IR_TX, 50000))
            wave.append(pigpio.pulse(0, 1 << IR_TX, 50000))

        pi.wave_clear()
        pi.wave_add_generic(wave)
        wid = pi.wave_create()

        pi.wave_send_once(wid)
        while pi.wave_tx_busy():
            time.sleep(0.001)

        pi.wave_delete(wid)

        D.show_message("IR LED Test", [
            "Test complete",
            "Camera should see",
            "purple/white blink",
            "Press A"
        ], color="GREEN")
        wait_back()

    except Exception as e:
        show_error("LED Test Error", e)

    finally:
        try:
            pi.write(IR_TX, 0)
            pi.stop()
        except Exception:
            pass


def view_code_info(name):
    db = load_db()
    code = db.get(name)

    if not code:
        D.show_message("IR Info", ["Code not found", "Press A"], color="RED")
        wait_back()
        return

    pulses = code.get("pulses", [])
    lines = [
        name[:20],
        f"Pulses: {len(pulses)}",
        f"Len: {total_duration_ms(pulses)}ms",
        f"Carrier: {code.get('carrier_hz', CARRIER_HZ)}",
        "Press A",
    ]

    D.show_message("IR Info", lines)
    wait_back()


def run():
    ensure_db()

    selected = 0

    while True:
        db = load_db()
        codes = list(db.keys())

        items = codes + [
            "[Learn new code]",
            "[Test IR LED]",
            "[Back]",
        ]

        if selected >= len(items):
            selected = 0

        D.draw_screen("IR Remote", items, selected)
        key = D.wait_key()

        if key == "up":
            selected = (selected - 1) % len(items)

        elif key == "down":
            selected = (selected + 1) % len(items)

        elif key == "back":
            return

        elif key == "select":
            chosen = items[selected]

            if chosen == "[Back]":
                return

            elif chosen == "[Learn new code]":
                learn_code()

            elif chosen == "[Test IR LED]":
                test_ir_led()

            else:
                send_menu(chosen)
