# The purpose of this code is to compile a JSON project into a binary config file and output it.
# usage: python compiler.py examples/hello.dash.json hello.dash.bin

import json
import struct
import sys
import zlib

NO_INDEX = 0xFFFF
HEADER_SIZE = 64
CRC_OFFSET = 0x3C

# (section id, record size), all 12 sections must be in the file even if empty
SECTIONS = [
    (0x01, 64),     # SETTINGS
    (0x02, 48),     # SIGNALS
    (0x03, 16),     # RXMSGS
    (0x04, 8),      # VALUES
    (0x05, 32),     # PAGES
    (0x06, 64),     # WIDGETS
    (0x07, 32),     # ALARMS
    (0x08, 32),     # LEDRULES
    (0x09, 8),      # THEME
    (0x0A, 32),     # ASSETS
    (0x0B, 0),      # ASSETDATA
    (0x0F, 0),      # STRINGS
]

WIDGET_TYPES = {"text": 1, "rect": 6}
ALIGN = {"left": 0, "center": 1, "right": 2}


def round_up_16(n):
    return (n + 15) // 16 * 16


def add_string(strings, text):
    if text in strings["offsets"]:
        return strings["offsets"][text]
    offset = len(strings["data"])
    strings["data"] += text.encode("utf-8") + b"\0"
    strings["offsets"][text] = offset
    return offset


def add_color(palette, color):
    if color is None:
        return NO_INDEX
    argb = 0xFF000000 | int(color[1:], 16)
    if argb not in palette:
        palette.append(argb)
    return palette.index(argb)


def make_widget(w, strings, palette):
    rec = b""
    rec += struct.pack("<B", WIDGET_TYPES[w["type"]])
    rec += struct.pack("<B", 0)
    rec += struct.pack("<H", NO_INDEX)  # no signal yet
    rec += struct.pack("<hhHH", w["x"], w["y"], w["w"], w["h"])
    rec += struct.pack("<H", add_color(palette, w.get("color", "#FFFFFF")))
    rec += struct.pack("<H", add_color(palette, w.get("background")))
    rec += struct.pack("<H", w.get("font", 0))
    rec += bytes(2)
    rec += struct.pack("<H", 0)  # dl cost, TODO
    rec += bytes(2)

    if w["type"] == "text":
        rec += struct.pack("<I", add_string(strings, w.get("text", "")))
        rec += struct.pack("<B", ALIGN[w.get("align", "left")])
        rec += struct.pack("<B", w.get("max_chars", 16))
    else:
        rec += struct.pack("<B", w.get("radius", 0))
    return rec.ljust(64, b"\0")


def make_page(name_offset, background, first_widget, widget_count):
    rec = b""
    rec += struct.pack("<I", name_offset)
    rec += struct.pack("<HH", first_widget, widget_count)
    rec += struct.pack("<I", 0)
    rec += struct.pack("<i", 0)
    rec += struct.pack("<H", background)
    rec += struct.pack("<H", NO_INDEX)
    rec += struct.pack("<H", 0)
    return rec.ljust(32, b"\0")


def make_settings():
    rec = b""
    rec += struct.pack("<III", 500000, 500000, 2000000)
    rec += struct.pack("<BB", 1, 10)
    rec += struct.pack("<HHH", 0, NO_INDEX, NO_INDEX)
    rec += struct.pack("<f", 0.0)
    rec += struct.pack("<BBBB", 0, 0, 255, 100)
    return rec.ljust(64, b"\0")


def compile_project(project):
    strings = {"data": bytearray(b"\0"), "offsets": {"": 0}}
    palette = []

    pages = b""
    widgets = b""
    widget_count = 0
    for page in project["pages"]:
        background = add_color(palette, page.get("background", "#000000"))
        name_offset = add_string(strings, page.get("name", ""))
        first = widget_count
        for w in page["widgets"]:
            widgets += make_widget(w, strings, palette)
            widget_count += 1
        pages += make_page(name_offset, background, first, widget_count - first)

    theme = b""
    for argb in palette:
        theme += struct.pack("<I", argb) + bytes(4)

    content = {
        0x01: (make_settings(), 1),
        0x05: (pages, len(project["pages"])),
        0x06: (widgets, widget_count),
        0x09: (theme, len(palette)),
        0x0F: (bytes(strings["data"]), 0),
    }

    table = b""
    data = b""
    start = HEADER_SIZE + 16 * len(SECTIONS)
    offset = start
    for section_id, record_size in SECTIONS:
        section_bytes, count = content.get(section_id, (b"", 0))
        offset = round_up_16(offset)
        data = data.ljust(offset - start, b"\0") + section_bytes
        table += struct.pack("<HHIIHH", section_id, 1, offset, len(section_bytes), count, record_size)
        offset += len(section_bytes)
    total_size = round_up_16(offset)
    data = data.ljust(total_size - start, b"\0")

    header = b"PGRC"
    header += struct.pack("<HH", 1, 0)
    header += struct.pack("<H", project["schema_version"])
    header += struct.pack("<H", HEADER_SIZE)
    header += struct.pack("<I", total_size)
    header += struct.pack("<I", 0x00010000)
    header += struct.pack("<HHI", len(SECTIONS), 16, HEADER_SIZE)
    header += struct.pack("<I", 0)
    header += struct.pack("<I", project["project"].get("revision", 0))
    header += bytes(4)
    header += project["project"]["name"].encode("utf-8")[:15].ljust(16, b"\0")
    header += bytes(4)
    header += struct.pack("<I", 0)

    blob = bytearray(header + table + data)
    # crc is calculated with the crc field set to 0
    crc = zlib.crc32(blob) & 0xFFFFFFFF
    blob[CRC_OFFSET:CRC_OFFSET + 4] = struct.pack("<I", crc)
    return bytes(blob)


def main():
    if len(sys.argv) != 3:
        print("usage: python blobgen.py <project.json> <output.bin>")
        return
    with open(sys.argv[1], encoding="utf-8") as f:
        project = json.load(f)
    blob = compile_project(project)
    with open(sys.argv[2], "wb") as f:
        f.write(blob)
    crc = struct.unpack_from("<I", blob, CRC_OFFSET)[0]
    print("%s: %d bytes, CRC32 0x%08X" % (sys.argv[2], len(blob), crc))
    for off in range(0, len(blob), 16):
        print("%04X: %s" % (off, blob[off:off + 16].hex(" ").upper()))


if __name__ == "__main__":
    main()