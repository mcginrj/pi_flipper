# modules/ir.py

import os
import json
import time
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
CAPTURE_END_GAP_SECONDS = 0.18

# Keep this low so pigpio does not get overloaded.
MAX_WAVE_PULSES = 9000


def ensure_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)

    if not os.path.exists(DB):
        with open(DB, "w") as f:
            json.dump({}, f, indent=2)


def load_db():
    ensure_db()

    try:
        with open(DB, "r") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

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


def start_pigpio_if_needed():
    pi = pigpio.pi()

    if pi.connected:
        pi.stop()
        return True

    try:
        subprocess.run(
            ["sudo", "systemctl", "start", "pigpiod"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        time.sleep(0.5)
    except Exception:
        pass

    pi = pigpio.pi()

    if pi.connected:
        pi.stop()
        return True

    return False


def normalize_pulses(pulses):
    clean = []

    for item in pulses:
        if not isinstance(item, (list, tuple)):
            continue

        if len(item) != 2:
            continue

        try:
            state = int(item[0])
            dur = int(item[1])
        except Exception:
            continue

        # Filter tiny glitches.
        if dur < 80:
            continue

        # Cap extremely long gaps.
        if dur > 200000:
            dur = 200000

        clean.append([state, dur])

    return clean


def total_duration_ms(pulses):
    try:
        return int(sum(int(p[1]) for p in pulses) / 1000)
    except Exception:
        return 0


def next_code_name(db):
    i = 1

    while f"code_{i}" in db:
        i += 1

    return f"code_{i}"


def capture_pulses():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(IR_RX, GPIO.IN)

    pulses = []

    last_state = GPIO.input(IR_RX)
    last_time = time.time()

    deadline = time.time() + MAX_CAPTURE_SECONDS
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
        "pulse_count": len(pulses),
        "duration_ms": total_duration_ms(pulses),
        "pulses": pulses
    }

    save_db(db)

    D.show_message("Saved IR", [
        f"Name: {name}",
        f"Pulses: {len(pulses)}",
        f"Len: {total_duration_ms(pulses)}ms",
        "Press A"
    ], color="GREEN")

    wait_back()


def carrier_pulses(duration_us):
    """
    Build 38 kHz carrier pulses for a mark period.
    """
    period = int(1_000_000 / CARRIER_HZ)
    on_time = max(1, int(period * DUTY_CYCLE))
    off_time = max(1, period - on_time)

    cycles = max(1, int(duration_us / period))

    pulses = []

    for _ in range(cycles):
        pulses.append(pigpio.pulse(1 << IR_TX, 0, on_time))
        pulses.append(pigpio.pulse(0, 1 << IR_TX, off_time))

    return pulses


def build_wave_from_code(code):
    raw = code.get("pulses", [])
    pulses = normalize_pulses(raw)

    wave = []

    for state, dur in pulses:
        # VS1838B receiver output is normally active-low.
        # state 0 usually means IR carrier was present.
        if int(state) == 0:
            wave.extend(carrier_pulses(int(dur)))
        else:
            wave.append(pigpio.pulse(0, 1 << IR_TX, int(dur)))

        if len(wave) > MAX_WAVE_PULSES:
            raise RuntimeError("IR code too large")

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
            "Press A"
        ], color="RED")
        wait_back()
        return

    pi = pigpio.pi()

    if not pi.connected:
        D.show_message("pigpio Error", ["No connection", "Press A"], color="RED")
        wait_back()
        return

    try:
        pi.set_mode(IR_TX, pigpio.OUTPUT)
        pi.write(IR_TX, 0)

        wave = build_wave_from_code(db[name])

        if not wave:
            D.show_message("IR Error", ["Empty signal", "Press A"], color="RED")
            wait_back()
            return

        pi.wave_clear()
        pi.wave_add_generic(wave)
        wid = pi.wave_create()

        if wid < 0:
            raise RuntimeError(f"wave_create {wid}")

        for _ in range(repeat):
            pi.wave_send_once(wid)

            while pi.wave_tx_busy():
                time.sleep(0.001)

            time.sleep(0.09)

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
            pi.wave_clear()
            pi.write(IR_TX, 0)
            pi.stop()
        except Exception:
            pass


def test_ir_led():
    """
    Simple safe LED test.
    Uses hardware PWM briefly so pigpio does not get overloaded with a huge wave.
    """
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

    if not pi.connected:
        D.show_message("pigpio Error", ["No connection", "Press A"], color="RED")
        wait_back()
        return

    try:
        pi.set_mode(IR_TX, pigpio.OUTPUT)
        pi.write(IR_TX, 0)

        # Blink 38 kHz carrier in short bursts.
        # 330000 duty = about 33%.
        for _ in range(8):
            pi.hardware_PWM(IR_TX, CARRIER_HZ, 330000)
            time.sleep(0.08)
            pi.hardware_PWM(IR_TX, 0, 0)
            pi.write(IR_TX, 0)
            time.sleep(0.08)

        D.show_message("IR LED Test", [
            "Test complete",
            "Check camera",
            "for blinking",
            "Press A"
        ], color="GREEN")

        wait_back()

    except Exception as e:
        show_error("LED Test Error", e)

    finally:
        try:
            pi.hardware_PWM(IR_TX, 0, 0)
            pi.write(IR_TX, 0)
            pi.stop()
        except Exception:
            pass


def delete_code(name):
    db = load_db()

    if name in db:
        del db[name]
        save_db(db)

        D.show_message("Deleted", [
            name[:20],
            "Press A"
        ], color="GREEN")
    else:
        D.show_message("Delete", [
            "Code not found",
            "Press A"
        ], color="RED")

    wait_back()


def view_code_info(name):
    db = load_db()
    code = db.get(name)

    if not code:
        D.show_message("IR Info", ["Code not found", "Press A"], color="RED")
        wait_back()
        return

    pulses = code.get("pulses", [])

    D.show_message("IR Info", [
        name[:20],
        f"Pulses: {len(pulses)}",
        f"Len: {total_duration_ms(pulses)}ms",
        f"Carrier: {code.get('carrier_hz', CARRIER_HZ)}",
        "Press A"
    ])

    wait_back()


def code_action_menu(name):
    menu = [
        "Send Once",
        "Send 3 Times",
        "Code Info",
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

            elif choice == "Code Info":
                view_code_info(name)

            elif choice == "Delete Code":
                delete_code(name)
                return

            elif choice == "Back":
                return


def run():
    ensure_db()

    selected = 0
    per_page = 6

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

        start = (selected // per_page) * per_page
        visible = items[start:start + per_page]

        D.draw_screen("IR Remote", visible, selected - start)
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
                code_action_menu(chosen)
