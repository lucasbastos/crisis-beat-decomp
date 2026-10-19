#!/usr/bin/env python3
"""Find PS1 TIM images in files or pack entries and convert them to PNG.

  python tools/tim2png.py out/tims disc/GALLERY.0              # scan whole files
  python tools/tim2png.py out/tims disc/DATA.0 --entry 0 1 105 # scan pack entries
  python tools/tim2png.py out/tims disc/DATA.0 --all-entries   # every entry

TIMs are found anywhere in the data (4-byte aligned), so images inside
sub-archives are picked up too. A candidate is accepted only when its block
sizes agree with its dimensions. Output: <out>/<source>[_<entry>]_<offset>.png
plus <out>/index.tsv. Colour 0x0000 is written as fully transparent, matching
how the PS1 GPU treats it (use --opaque for full-screen art). 4/8bpp images
use the first CLUT row unless --all-cluts is given.
"""
import argparse
import struct
import sys
import zlib
from pathlib import Path

BPP = {0: 4, 1: 8, 2: 16, 3: 24}


def png(width, height, rows):
    """Encode RGBA rows (bytes, 4*width each) as a PNG file."""
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
    raw = b"".join(b"\0" + r for r in rows)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


OPAQUE = False  # set by --opaque: draw colour 0x0000 as black instead of transparent


def rgba(c):
    if c == 0 and not OPAQUE:
        return b"\0\0\0\0"
    r, g, b = c & 31, (c >> 5) & 31, (c >> 10) & 31
    return bytes(((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2), 255))


def parse_tim(data, off):
    """Return a dict describing a valid TIM at off, or None."""
    if off + 8 > len(data) or struct.unpack_from("<I", data, off)[0] != 0x10:
        return None
    flags = struct.unpack_from("<I", data, off + 4)[0]
    if flags & ~0xB or (flags & 7) not in BPP:
        return None
    bpp, has_clut = BPP[flags & 7], bool(flags & 8)
    if has_clut != (bpp <= 8):
        return None  # only accept the common combinations
    pos, clut = off + 8, None
    if has_clut:
        if pos + 12 > len(data):
            return None
        bnum, cx, cy, cw, ch = struct.unpack_from("<I4H", data, pos)
        if not cw or not ch or bnum != 12 + cw * ch * 2 or pos + bnum > len(data):
            return None
        if cw != (16 if bpp == 4 else 256) and cw % 16:
            return None
        clut = [struct.unpack_from(f"<{cw}H", data, pos + 12 + row * cw * 2) for row in range(ch)]
        pos += bnum
    if pos + 12 > len(data):
        return None
    bnum, x, y, w, h = struct.unpack_from("<I4H", data, pos)
    if not w or not h or w > 1024 or h > 512 or bnum != 12 + w * h * 2 or pos + bnum > len(data):
        return None
    width = {4: w * 4, 8: w * 2, 16: w, 24: w * 2 // 3}[bpp]
    return {"bpp": bpp, "clut": clut, "width": width, "height": h, "vram": (x, y),
            "pixels": data[pos + 12:pos + bnum], "stride": w * 2, "end": pos + bnum}


def render(tim, palette):
    rows = []
    px, stride, width = tim["pixels"], tim["stride"], tim["width"]
    for y in range(tim["height"]):
        line = px[y * stride:(y + 1) * stride]
        if tim["bpp"] == 4:
            row = b"".join(rgba(palette[(b >> s) & 15]) for b in line for s in (0, 4))
        elif tim["bpp"] == 8:
            row = b"".join(rgba(palette[b]) for b in line)
        elif tim["bpp"] == 16:
            row = b"".join(rgba(c) for c in struct.unpack(f"<{width}H", line))
        else:
            row = b"".join(bytes(line[i:i + 3]) + b"\xff" for i in range(0, width * 3, 3))
        rows.append(row[:width * 4])
    return png(width, tim["height"], rows)


def scan(data):
    off = 0
    while True:
        off = data.find(b"\x10\0\0\0", off)  # jump to the next TIM magic candidate
        if off < 0:
            return
        if off % 4:
            off += 4 - off % 4
            continue
        tim = parse_tim(data, off)
        if tim:
            yield off, tim
            off = (tim["end"] + 3) & ~3
        else:
            off += 4


def pack_entries(data):
    table_size = struct.unpack_from("<I", data, 0)[0]
    offsets = [o for o in struct.unpack_from(f"<{table_size // 4}I", data, 0) if o]
    bounds = offsets + [len(data)]
    return [(bounds[i], bounds[i + 1]) for i in range(len(offsets))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("source")
    sel = ap.add_mutually_exclusive_group()
    sel.add_argument("--entry", type=int, nargs="+", help="treat source as a pack, scan these entries")
    sel.add_argument("--all-entries", action="store_true", help="treat source as a pack, scan every entry")
    ap.add_argument("--all-cluts", action="store_true", help="write one PNG per CLUT row")
    ap.add_argument("--opaque", action="store_true",
                    help="draw colour 0x0000 as black (for full-screen art) instead of transparent")
    args = ap.parse_args()
    global OPAQUE
    OPAQUE = args.opaque

    data = Path(args.source).read_bytes()
    stem = Path(args.source).name.replace(".", "_")
    if args.entry or args.all_entries:
        entries = pack_entries(data)
        wanted = range(len(entries)) if args.all_entries else args.entry
        jobs = [(f"{stem}_{i:04d}", data[entries[i][0]:entries[i][1]]) for i in wanted]
    else:
        jobs = [(stem, data)]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    index = out / "index.tsv"
    new_index = not index.exists()
    count = 0
    with open(index, "a") as idx:
        if new_index:
            idx.write("file\tsource\toffset\tbpp\twidth\theight\tvram_x\tvram_y\tcluts\n")
        for name, blob in jobs:
            for off, tim in scan(blob):
                palettes = tim["clut"] or [None]
                for n, pal in enumerate(palettes if args.all_cluts else palettes[:1]):
                    fname = f"{name}_{off:06x}" + (f"_c{n}" if args.all_cluts and len(palettes) > 1 else "") + ".png"
                    (out / fname).write_bytes(render(tim, pal))
                    idx.write(f"{fname}\t{name}\t{off:#x}\t{tim['bpp']}\t{tim['width']}\t{tim['height']}"
                              f"\t{tim['vram'][0]}\t{tim['vram'][1]}\t{len(palettes) if tim['clut'] else 0}\n")
                    count += 1
    print(f"wrote {count} PNGs to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
