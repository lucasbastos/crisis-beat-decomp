#!/usr/bin/env python3
"""List (and optionally extract) the sections of sub-archives inside DATA.0 entries.

Sub-archives use the same layout as DATA.0 itself: a table of ascending u32
offsets whose first value is the table size (0x10, 0x200, 0x400, ...), with
unused slots zeroed. Each section runs to the next offset (the last to the
end of the entry). See notes/data0.md.

Usage: python tools/subarc_list.py disc/DATA.0 1 105 2016 [--extract out/sub]
"""
import argparse
import collections
import struct
from pathlib import Path

KNOWN = {b"pBAV": "VAB header", b"\x10\0\0\0": "TIM?", b"\x73\x01\x10\x87": "compressed?"}


def pack_entries(data):
    table_size = struct.unpack_from("<I", data, 0)[0]
    offsets = [o for o in struct.unpack_from(f"<{table_size // 4}I", data, 0) if o]
    bounds = offsets + [len(data)]
    return [(bounds[i], bounds[i + 1]) for i in range(len(offsets))]


def sections(blob):
    """Return section (start, end) pairs, or None if blob is not a sub-archive."""
    if len(blob) < 4:
        return None
    first = struct.unpack_from("<I", blob, 0)[0]
    if first < 4 or first % 4 or first > min(len(blob), 0x2000):
        return None
    table = list(struct.unpack_from(f"<{first // 4}I", blob, 0))
    while table and table[-1] == 0:
        table.pop()
    if any(b <= a for a, b in zip(table, table[1:])) or table[-1] > len(blob):
        return None
    bounds = table + [len(blob)]
    return list(zip(bounds, bounds[1:]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack")
    ap.add_argument("entry", type=int, nargs="+")
    ap.add_argument("--extract", metavar="DIR")
    args = ap.parse_args()

    data = Path(args.pack).read_bytes()
    entries = pack_entries(data)
    for e in args.entry:
        blob = data[entries[e][0]:entries[e][1]]
        secs = sections(blob)
        if not secs:
            print(f"entry {e}: not a sub-archive")
            continue
        heads = collections.Counter(blob[a:a + 4] for a, _ in secs)
        print(f"entry {e}: {len(secs)} sections; common heads: "
              + ", ".join(f"{h.hex()} x{n}" for h, n in heads.most_common(4)))
        for i, (a, b) in enumerate(secs):
            kind = KNOWN.get(blob[a:a + 4], "zeros (VAB body?)" if not any(blob[a:a + 16]) else "")
            print(f"  [{i:3d}] {a:#8x} {b - a:#8x}  {blob[a:a + 12].hex(' ')}  {kind}")
            if args.extract:
                out = Path(args.extract) / f"{e:04d}"
                out.mkdir(parents=True, exist_ok=True)
                (out / f"{i:03d}.bin").write_bytes(blob[a:b])


if __name__ == "__main__":
    main()
