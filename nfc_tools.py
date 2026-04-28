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

# MIFARE Ultralight MF01CU1 usually has pages 0-15.
# Pages 0-3 contain UID/manufacturer/lock/CC data.
# Pages 4-15 are user memory.
RAW_START_PAGE = 4
RAW_END_PAGE = 15


def wait_back():
    while True:
        key = D.wait_key()
        if key in ["back", "select", "shutdown"]:
            return key


def show_error(e):
    D.show_message("NFC Error", [str(e)[:28], "Press A"], color="RED")
    wait_back()


def safe_uid(tag):
    try:
        return binascii.hexlify(tag.identifier).decode().upper()
    except Exception:
        return "Unknown"


def open_reader():
    return nfc.ContactlessFrontend(NFC_PORT)


def read_tag_info():
    clf = None
    try:
        D.show_message("NFC Info", ["Tap tag", "Hold steady..."])
        clf = open_reader()
        tag = clf.connect(rdwr={"on-connect": lambda tag: False})

        uid = safe_uid(tag)

        lines = [
            "Tag Found",
            str(tag)[:22],
            f"UID: {uid[:18]}",
        ]

        try:
            ndef_obj = tag.ndef
        except Exception:
            ndef_obj = None

        if ndef_obj:
            lines += [
                "NDEF: Yes",
                f"Records: {len(ndef_obj.records)}",
                f"Size: {ndef_obj.length}/{ndef_obj.capacity}",
                f"Writable: {ndef_obj.is_writeable}",
            ]
        else:
            lines += ["NDEF: No/Unreadable"]

        lines.append("Press A")
        D.show_message("NFC Info", lines[:9])
        wait_back()

    finally:
        if clf:
            clf.close()


def dump_ndef():
    clf = None
    try:
        D.show_message("NDEF", ["Tap tag", "Hold steady..."])
        clf = open_reader()
        tag = clf.connect(rdwr={"on-connect": lambda tag: False})

        try:
            ndef_obj = tag.ndef
        except Exception:
            ndef_obj = None

        if not ndef_obj:
            D.show_message("NDEF Dump", ["No NDEF data", "Press A"])
            wait_back()
            return

        records = list(ndef_obj.records)

        if not records:
            D.show_message("NDEF Dump", ["NDEF exists", "No records", "Press A"])
            wait_back()
            return

        lines = [
            f"Records: {len(records)}",
            f"Size: {ndef_obj.length}/{ndef_obj.capacity}",
        ]

        for i, record in enumerate(records[:3]):
            lines.append(f"{i+1}: {record.type[:16]}")
            lines.append(str(record)[:20])

        lines.append("Press A")
        D.show_message("NDEF Dump", lines[:9])
        wait_back()

    finally:
        if clf:
            clf.close()


def write_test_text():
    clf = None
    try:
        D.show_message("NFC Write", ["Tap blank tag", "Hold steady..."])
        clf = open_reader()
        tag = clf.connect(rdwr={"on-connect": lambda tag: False})

        try:
            ndef_obj = tag.ndef
        except Exception:
            ndef_obj = None

        if not ndef_obj:
            D.show_message("NFC Write", ["Tag has no", "NDEF area", "Press A"])
        elif not ndef_obj.is_writeable:
            D.show_message("NFC Write", ["Tag not writable", "Press A"])
        else:
            ndef_obj.records = [ndef.TextRecord("Portable IoT Tool")]
            D.show_message("NFC Write", ["Text written", "Press A"], color="GREEN")

        wait_back()

    finally:
        if clf:
            clf.close()


def copy_ndef():
    source_records = None
    source_length = 0

    clf = None
    try:
        D.show_message("NFC Copy", ["Tap SOURCE tag", "Hold steady..."])
        clf = open_reader()
        src = clf.connect(rdwr={"on-connect": lambda tag: False})

        try:
            src_ndef = src.ndef
        except Exception:
            src_ndef = None

        if not src_ndef:
            D.show_message("NFC Copy", ["Source has no", "NDEF data", "Press A"])
            wait_back()
            return

        source_records = list(src_ndef.records)
        source_length = src_ndef.length

        D.show_message("NFC Copy", [
            f"Copied {len(source_records)} recs",
            "Remove source",
            "Press A"
        ])
        wait_back()

    finally:
        if clf:
            clf.close()

    clf = None
    try:
        D.show_message("NFC Copy", ["Tap BLANK tag", "Hold steady..."])
        clf = open_reader()
        dst = clf.connect(rdwr={"on-connect": lambda tag: False})

        try:
            dst_ndef = dst.ndef
        except Exception:
            dst_ndef = None

        if not dst_ndef:
            D.show_message("NFC Copy", ["Dest has no", "NDEF area", "Press A"])
        elif not dst_ndef.is_writeable:
            D.show_message("NFC Copy", ["Dest not writable", "Press A"])
        elif dst_ndef.capacity < source_length:
            D.show_message("NFC Copy", ["Dest too small", "Press A"])
        else:
            dst_ndef.records = source_records
            D.show_message("NFC Copy", ["Write complete", "Press A"], color="GREEN")

        wait_back()

    finally:
        if clf:
            clf.close()


def read_raw_pages(tag, start_page=RAW_START_PAGE, end_page=RAW_END_PAGE):
    """
    Reads Type 2 tag pages.
    nfcpy tag.read(page) returns 16 bytes = 4 pages at once.
    We split that into individual 4-byte pages.
    """
    pages = {}

    page = start_page
    while page <= end_page:
        block = tag.read(page)

        for offset in range(0, 16, 4):
            page_num = page + (offset // 4)
            if page_num <= end_page:
                pages[page_num] = bytes(block[offset:offset + 4])

        page += 4

    return pages


def dump_raw_pages():
    clf = None
    try:
        D.show_message("Raw Dump", ["Tap tag", "Hold steady..."])
        clf = open_reader()
        tag = clf.connect(rdwr={"on-connect": lambda tag: False})

        pages = read_raw_pages(tag)

        lines = []
        for page in sorted(pages.keys()):
            lines.append(f"P{page}: {pages[page].hex().upper()}")

        # Show first screen only because LCD is small.
        lines.append("Press A")
        D.show_message("Raw Pages", lines[:9])
        wait_back()

    finally:
        if clf:
            clf.close()


def clone_raw_pages():
    source_pages = {}

    clf = None
    try:
        D.show_message("Raw Clone", ["Tap SOURCE tag", "Hold steady..."])
        clf = open_reader()
        src = clf.connect(rdwr={"on-connect": lambda tag: False})

        source_pages = read_raw_pages(src)

        D.show_message("Raw Clone", [
            f"Copied P{RAW_START_PAGE}-{RAW_END_PAGE}",
            "Remove source",
            "Press A"
        ])
        wait_back()

    finally:
        if clf:
            clf.close()

    clf = None
    try:
        D.show_message("Raw Clone", ["Tap BLANK tag", "Hold steady..."])
        clf = open_reader()
        dst = clf.connect(rdwr={"on-connect": lambda tag: False})

        written = 0
        failed = 0

        for page in sorted(source_pages.keys()):
            try:
                dst.write(page, source_pages[page])
                written += 1
                time.sleep(0.05)
            except Exception:
                failed += 1

        if failed == 0:
            D.show_message("Raw Clone", [
                "Write complete",
                f"Pages written: {written}",
                "Press A"
            ], color="GREEN")
        else:
            D.show_message("Raw Clone", [
                "Partial write",
                f"OK: {written}",
                f"Fail: {failed}",
                "Press A"
            ], color="YELLOW")

        wait_back()

    finally:
        if clf:
            clf.close()


def run():
    menu = [
        "Read Tag Info",
        "Dump NDEF",
        "Copy NDEF",
        "Write Test Text",
        "Dump Raw Pages",
        "Clone Raw Pages",
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
                elif choice == "Copy NDEF":
                    copy_ndef()
                elif choice == "Write Test Text":
                    write_test_text()
                elif choice == "Dump Raw Pages":
                    dump_raw_pages()
                elif choice == "Clone Raw Pages":
                    clone_raw_pages()
                elif choice == "Back":
                    return

            except Exception as e:
                show_error(e)
