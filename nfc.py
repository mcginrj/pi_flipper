import nfc, binascii, display as D

def run():
    D.show_message("NFC Reader", ["Hold card to reader...", "Press A to cancel"])

    result = {"found": False, "uid": "", "type": ""}

    def connected(tag):
        result["found"] = True
        result["uid"]   = binascii.hexlify(tag.identifier).decode().upper()
        result["type"]  = tag.type
        return False  # don't keep polling

    import RPi.GPIO as GPIO
    import threading, time

    stopped = [False]

    def poll():
        try:
            clf = nfc.ContactlessFrontend('usb')
            clf.connect(rdwr={'on-connect': connected}, terminate=lambda: stopped[0])
            clf.close()
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=poll, daemon=True)
    t.start()

    while t.is_alive():
        if not GPIO.input(D.KEY_A):
            stopped[0] = True
            break
        time.sleep(0.1)

    if result["found"]:
        D.show_message("Card Found!", [
            f"UID: {result['uid']}",
            f"Type: {result['type']}",
            "",
            "Press A to go back"
        ], color="GREEN")
    else:
        D.show_message("NFC Reader", ["No card found", "Press A to go back"])
    D.wait_key()
