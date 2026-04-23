# modules/ir.py
import RPi.GPIO as GPIO, pigpio, time, json, os
import display as D

IR_RX  = 17
IR_TX  = 18
DB     = os.path.expanduser("~/piflipger/data/ir_codes.json")
db     = json.load(open(DB)) if os.path.exists(DB) else {}

def run():
    items  = list(db.keys()) + ["[Learn new code]", "[Back]"]
    sel    = 0

    while True:
        D.draw_screen("IR Remote", items, sel)
        key = D.wait_key()

        if key == 'up':
            sel = (sel - 1) % len(items)
        elif key == 'down':
            sel = (sel + 1) % len(items)
        elif key == 'back':
            return
        elif key == 'select':
            chosen = items[sel]
            if chosen == "[Back]":
                return
            elif chosen == "[Learn new code]":
                learn_code()
                items = list(db.keys()) + ["[Learn new code]","[Back]"]
            else:
                send_code(chosen)

def learn_code():
    D.show_message("Learning IR", ["Point remote at sensor", "and press a button..."])
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(IR_RX, GPIO.IN)
    pulses = []
    last_state = 1
    last_time  = time.time()
    deadline   = time.time() + 5

    while time.time() < deadline:
        state = GPIO.input(IR_RX)
        if state != last_state:
            duration = int((time.time() - last_time) * 1_000_000)
            pulses.append((last_state, duration))
            last_state = state
            last_time  = time.time()
            if len(pulses) > 10:
                deadline = time.time() + 0.1

    if len(pulses) > 4:
        name = f"code_{len(db)+1}"
        db[name] = pulses
        json.dump(db, open(DB,'w'))
        D.show_message("Saved!", [f"Saved as: {name}", "Press A to go back"], color="GREEN")
    else:
        D.show_message("Failed", ["No signal detected", "Press A to try again"])
    D.wait_key()

def send_code(name):
    if name not in db: return
    pi = pigpio.pi()
    wave = []
    for state, dur in db[name]:
        if state == 0:
            wave.append(pigpio.pulse(1 << IR_TX, 0, dur))
        else:
            wave.append(pigpio.pulse(0, 1 << IR_TX, dur))
    pi.set_mode(IR_TX, pigpio.OUTPUT)
    pi.wave_clear()
    pi.wave_add_generic(wave)
    wid = pi.wave_create()
    pi.wave_send_once(wid)
    while pi.wave_tx_busy(): time.sleep(0.001)
    pi.wave_delete(wid)
    pi.stop()
    D.show_message("IR Sent", [f"Sent: {name}", "Press A to go back"])
    D.wait_key()
