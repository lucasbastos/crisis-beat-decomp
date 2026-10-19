#!/usr/bin/env python3
"""List entries of a Crisis Beat .0 pack file (DATA.0, GALLERY.0).

Working hypothesis (see notes/data0.md): the file starts with a table of
little-endian u32 byte offsets, sector aligned, one per entry. The first
offset equals the table size. Entry i spans offsets[i]..offsets[i+1]; the
last entry runs to end of file. Zero padding fills the unused table slots.

Usage: python tools/pack_list.py disc/DATA.0 [--extract out/DATA]
"""
import argparse
import struct
from pathlib import Path


def read_table(data):
    table_size = struct.unpack_from("<I", data, 0)[0]
    offsets = []
    for pos in range(0, table_size, 4):
        off = struct.unpack_from("<I", data, pos)[0]
        if off == 0:
            break
        offsets.append(off)
    return table_size, offsets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack")
    ap.add_argument("--extract", metavar="DIR")
    args = ap.parse_args()

    data = Path(args.pack).read_bytes()
    table_size, offsets = read_table(data)
    bounds = offsets + [len(data)]
    print(f"table size {table_size:#x}, {len(offsets)} entries, file size {len(data):#x}")

    for i, (start, end) in enumerate(zip(bounds, bounds[1:])):
        head = data[start:start + 8]
        flag = "" if start % 2048 == 0 and end >= start else "  <-- unexpected"
        print(f"{i:4d} {start:#010x} {end - start:#9x}  {head.hex(' ')}{flag}")
        if args.extract:
            out = Path(args.extract)
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{i:04d}.bin").write_bytes(data[start:end])


if __name__ == "__main__":
    main()
