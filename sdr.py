import subprocess, threading, display as D

results = []

def run():
    global results
    results = []
    D.show_message("SDR Scanner", ["Scanning 433 MHz...", "Press A to stop"])

    proc = subprocess.Popen(
        ["rtl_433", "-f", "433.92M", "-F", "json", "-T", "20"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    )

    import json, time, RPi.GPIO as GPIO
    deadline = time.time() + 20

    while time.time() < deadline:
        if not GPIO.input(D.KEY_A):
            proc.terminate()
            break
        line = proc.stdout.readline()
        if line:
            try:
                data = json.loads(line)
                label = data.get('model', 'Unknown') + " " + str(data.get('id',''))
                results.append(label[:35])
            except Exception:
                pass
        time.sleep(0.05)

    proc.terminate()

    if results:
        D.show_message("SDR Results", results[:8] + ["", "Press A to go back"])
    else:
        D.show_message("SDR Scanner", ["No signals detected", "Press A to go back"])
    D.wait_key()
