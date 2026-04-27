import nfc
import binascii
import display as D

NFC_PORT = "tty:serial0"
last_records = None


def wait_back():
    while True:
        key = D.wait_key()
        if key in ["back", "select", "shutdown"]:
            return


def read_tag():
    D.show_message("NFC", ["Tap tag now..."])

    clf = nfc.ContactlessFrontend(NFC_PORT)
    tag = clf.connect(rdwr={"on-connect": lambda tag: False})
    clf.close()

    uid = binascii.hexlify(tag.identifier).decode().upper()

    lines = [
        "Tag Found",
        str(tag)[:24],
        f"UID: {uid[:18]}",
    ]

    if tag.ndef:
        lines.append(f"NDEF: Yes")
        lines.append(f"Records: {len(tag.ndef.records)}")
        lines.append(f"Size: {tag.ndef.length}/{tag.ndef.capacity}")
    else:
        lines.append("NDEF: No")

    lines.append("Press A")
    D.show_message("NFC Info", lines)
    wait_back()


def dump_ndef():
    D.show_message("NFC", ["Tap tag to dump..."])

    clf = nfc.ContactlessFrontend(NFC_PORT)
    tag = clf.connect(rdwr={"on-connect": lambda tag: False})
    clf.close()

    if not tag.ndef:
        D.show_message("NFC Dump", ["No NDEF data", "Press A"])
        wait_back()
        return

    lines = []
    for i, record in enumerate(tag.ndef.records):
        lines.append(f"{i+1}: {record.type[:18]}")
        lines.append(str(record)[:22])

    lines.append("Press A")
    D.show_message("NDEF Dump", lines[:8])
    wait_back()


def copy_ndef():
    global last_records

    D.show_message("NFC Copy", ["Tap SOURCE tag..."])

    clf = nfc.ContactlessFrontend(NFC_PORT)
    src = clf.connect(rdwr={"on-connect": lambda tag: False})

    if not src.ndef:
        clf.close()
        D.show_message("NFC Copy", ["Source has no", "NDEF data", "Press A"])
        wait_back()
        return

    last_records = list(src.ndef.records)
    src_len = src.ndef.length
    src_cap = src.ndef.capacity

    D.show_message("NFC Copy", [
        f"Copied {len(last_records)} recs",
        f"Size: {src_len}/{src_cap}",
        "Tap BLANK tag..."
    ])

    dst = clf.connect(rdwr={"on-connect": lambda tag: False})

    if not dst.ndef:
        D.show_message("NFC Copy", ["Blank tag not", "NDEF formatted", "Press A"])
    elif not dst.ndef.is_writeable:
        D.show_message("NFC Copy", ["Destination not", "writable", "Press A"])
    elif dst.ndef.capacity < src_len:
        D.show_message("NFC Copy", ["Destination too", "small", "Press A"])
    else:
        dst.ndef.records = last_records
        D.show_message("NFC Copy", ["Write complete", "Press A"], color="GREEN")

    clf.close()
    wait_back()


def write_text():
    import ndef

    text = "Portable IoT Tool"

    D.show_message("NFC Write", ["Tap blank tag...", f"Text: {text[:16]}"])

    clf = nfc.ContactlessFrontend(NFC_PORT)
    tag = clf.connect(rdwr={"on-connect": lambda tag: False})

    if not tag.ndef:
        D.show_message("NFC Write", ["Tag not NDEF", "formatted", "Press A"])
    elif not tag.ndef.is_writeable:
        D.show_message("NFC Write", ["Tag not writable", "Press A"])
    else:
        tag.ndef.records = [ndef.TextRecord(text)]
        D.show_message("NFC Write", ["Text written", "Press A"], color="GREEN")

    clf.close()
    wait_back()


def run():
    menu = [
        "Read Tag Info",
        "Dump NDEF",
        "Copy NDEF Tag",
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
            choice = menu[selected]

            try:
                if choice == "Read Tag Info":
                    read_tag()
                elif choice == "Dump NDEF":
                    dump_ndef()
                elif choice == "Copy NDEF Tag":
                    copy_ndef()
                elif choice == "Write Test Text":
                    write_text()
                elif choice == "Back":
                    return
            except Exception as e:
                D.show_message("NFC Error", [str(e)[:28], "Press A"], color="RED")
                wait_back()
