import sys
import os
import time
import binascii
import importlib

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import display as D

nfc = importlib.import_module("nfc")
ndef = importlib.import_module("ndef")

NFC_PORT = "tty:serial0"


def wait_back():
    while True:
        key = D.wait_key()
        if key in ["back", "select", "shutdown"]:
            return key


def show_error(e):
    D.show_message("NFC Error", [str(e)[:28], "Press A"], color="RED")
    wait_back()


def get_tag(prompt):
    D.show_message("NFC", [prompt, "Tap and hold tag"])
    time.sleep(0.3)

    clf = nfc.ContactlessFrontend(NFC_PORT)
    try:
        tag = clf.connect(rdwr={"on-connect": lambda tag: False})
        time.sleep(0.2)
        return tag
    finally:
        clf.close()
        time.sleep(0.5)


def safe_uid(tag):
    try:
        return binascii.hexlify(tag.identifier).decode().upper()
    except Exception:
        return "Unknown"


def read_tag_info():
    tag = get_tag("Read Tag Info")
    uid = safe_uid(tag)

    D.show_message("NFC Info", [
        "Tag Found",
        str(tag)[:22],
        f"UID: {uid[:18]}",
        "Press A"
    ])
    wait_back()


def dump_ndef():
    tag = get_tag("Dump NDEF")

    try:
        ndef_obj = tag.ndef
    except Exception:
        ndef_obj = None

    if not ndef_obj:
        D.show_message("NDEF", ["No/Unreadable", "NDEF data", "Press A"])
        wait_back()
        return

    lines = [
        f"Records: {len(ndef_obj.records)}",
        f"Size: {ndef_obj.length}/{ndef_obj.capacity}",
    ]

    for i, record in enumerate(list(ndef_obj.records)[:3]):
        lines.append(f"{i+1}: {record.type[:16]}")

    lines.append("Press A")
    D.show_message("NDEF Dump", lines[:8])
    wait_back()


def write_test_text():
    tag = get_tag("Write Text Tag")

    try:
        ndef_obj = tag.ndef
    except Exception:
        ndef_obj = None

    if not ndef_obj:
        D.show_message("NFC Write", ["Tag has no NDEF", "Press A"])
    elif not ndef_obj.is_writeable:
        D.show_message("NFC Write", ["Tag not writable", "Press A"])
    else:
        ndef_obj.records = [ndef.TextRecord("Portable IoT Tool")]
        D.show_message("NFC Write", ["Text written", "Press A"], color="GREEN")

    wait_back()


def copy_ndef():
    src = get_tag("Tap SOURCE tag")

    try:
        src_ndef = src.ndef
    except Exception:
        src_ndef = None

    if not src_ndef:
        D.show_message("NFC Copy", ["Source has no", "NDEF data", "Press A"])
        wait_back()
        return

    records = list(src_ndef.records)
    length = src_ndef.length

    D.show_message("NFC Copy", [
        f"Copied {len(records)} recs",
        "Remove source",
        "Press A"
    ])
    wait_back()

    dst = get_tag("Tap BLANK tag")

    try:
        dst_ndef = dst.ndef
    except Exception:
        dst_ndef = None

    if not dst_ndef:
        D.show_message("NFC Copy", ["Dest has no", "NDEF area", "Press A"])
    elif not dst_ndef.is_writeable:
        D.show_message("NFC Copy", ["Dest not writable", "Press A"])
    elif dst_ndef.capacity < length:
        D.show_message("NFC Copy", ["Dest too small", "Press A"])
    else:
        dst_ndef.records = records
        D.show_message("NFC Copy", ["Write complete", "Press A"], color="GREEN")

    wait_back()


def run():
    menu = [
        "Read Tag Info",
        "Dump NDEF",
        "Copy NDEF",
        "Write Test Text",
        "Back",
    ]

    selected = 0

    while True:
        D.draw_screen("NFC Tools", menu, selected)
        key = D.wait_key()

        if key == "up":
            selected = (selected - 1) % len(menu)
        elif key == "down":
            selected = (selected + 1) % len(menu)
        elif key == "back":
            return
        elif key == "select":
            try:
                choice = menu[selected]

                if choice == "Read Tag Info":
                    read_tag_info()
                elif choice == "Dump NDEF":
                    dump_ndef()
                elif choice == "Copy NDEF":
                    copy_ndef()
                elif choice == "Write Test Text":
                    write_test_text()
                elif choice == "Back":
                    return

            except Exception as e:
                show_error(e)
