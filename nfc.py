import sys
import os
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

def get_tag(prompt):
    D.show_message("NFC", [prompt, "Hold tag steady..."])
    clf = None
    try:
        clf = nfc.ContactlessFrontend(NFC_PORT)
        tag = clf.connect(rdwr={"on-connect": lambda tag: False})
        return tag
    finally:
        if clf:
            clf.close()


def safe_uid(tag):
    try:
        return binascii.hexlify(tag.identifier).decode().upper()
    except Exception:
        return "Unknown"


def read_tag_info():
    tag = get_tag("Tap tag now")

    uid = safe_uid(tag)
    lines = [
        "Tag Found",
        str(tag)[:22],
        f"UID: {uid[:18]}",
    ]

    if tag.ndef:
        lines += [
            "NDEF: Yes",
            f"Records: {len(tag.ndef.records)}",
            f"Size: {tag.ndef.length}/{tag.ndef.capacity}",
            f"Writable: {tag.ndef.is_writeable}",
        ]
    else:
        lines += ["NDEF: No"]

    lines.append("Press A")
    D.show_message("NFC Info", lines[:9])
    wait_back()


def dump_ndef():
    tag = get_tag("Tap tag to dump")

    if not tag.ndef:
        D.show_message("NDEF Dump", ["No NDEF data", "Press A"])
        wait_back()
        return

    records = list(tag.ndef.records)

    if not records:
        D.show_message("NDEF Dump", ["NDEF exists", "No records", "Press A"])
        wait_back()
        return

    lines = []
    for i, record in enumerate(records[:4]):
        lines.append(f"{i+1}: {record.type[:18]}")
        lines.append(str(record)[:22])

    lines.append("Press A")
    D.show_message("NDEF Dump", lines[:9])
    wait_back()


def copy_ndef():
    D.show_message("NFC Copy", ["Tap SOURCE tag"])
    src = get_tag("Tap SOURCE tag")

    if not src.ndef:
        D.show_message("NFC Copy", ["Source has no", "NDEF data", "Press A"])
        wait_back()
        return

    records = list(src.ndef.records)
    src_len = src.ndef.length

    D.show_message("NFC Copy", [
        f"Copied {len(records)} recs",
        f"Size: {src_len}",
        "Remove source",
        "Press A"
    ])
    wait_back()

    dst = get_tag("Tap BLANK tag")

    if not dst.ndef:
        D.show_message("NFC Copy", ["Dest not NDEF", "formatted", "Press A"])
    elif not dst.ndef.is_writeable:
        D.show_message("NFC Copy", ["Dest not", "writable", "Press A"])
    elif dst.ndef.capacity < src_len:
        D.show_message("NFC Copy", ["Dest too small", "Press A"])
    else:
        dst.ndef.records = records
        D.show_message("NFC Copy", ["Write complete", "Press A"], color="GREEN")

    wait_back()


def write_test_text():
    text = "Portable IoT Tool"

    tag = get_tag("Tap blank tag")

    if not tag.ndef:
        D.show_message("NFC Write", ["Tag not NDEF", "formatted", "Press A"])
    elif not tag.ndef.is_writeable:
        D.show_message("NFC Write", ["Tag not writable", "Press A"])
    else:
        tag.ndef.records = [ndef.TextRecord(text)]
        D.show_message("NFC Write", ["Text written", text[:20], "Press A"], color="GREEN")

    wait_back()


def write_test_url():
    url = "https://example.com"

    tag = get_tag("Tap blank tag")

    if not tag.ndef:
        D.show_message("NFC URL", ["Tag not NDEF", "formatted", "Press A"])
    elif not tag.ndef.is_writeable:
        D.show_message("NFC URL", ["Tag not writable", "Press A"])
    else:
        tag.ndef.records = [ndef.UriRecord(url)]
        D.show_message("NFC URL", ["URL written", url[:20], "Press A"], color="GREEN")

    wait_back()


def run():
    menu = [
        "Read Tag Info",
        "Dump NDEF",
        "Copy NDEF Tag",
        "Write Test Text",
        "Write Test URL",
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
            choice = menu[selected]

            try:
                if choice == "Read Tag Info":
                    read_tag_info()
                elif choice == "Dump NDEF":
                    dump_ndef()
                elif choice == "Copy NDEF Tag":
                    copy_ndef()
                elif choice == "Write Test Text":
                    write_test_text()
                elif choice == "Write Test URL":
                    write_test_url()
                elif choice == "Back":
                    return

            except Exception as e:
                D.show_message("NFC Error", [str(e)[:28], "Press A"], color="RED")
                wait_back()
