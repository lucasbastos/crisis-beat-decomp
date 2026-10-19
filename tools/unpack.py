#!/usr/bin/env python3
"""Decompress Crisis Beat compressed streams and convert any TIMs to PNG.

Format (reimplemented from the exe; see notes/formats.md):
  stream  = block* 0x00                  each block unpacks into its own 0x2000 slot
  block   = method byte, then data       (Unpack_Block @ 0x8001DA78 dispatches)
    0x73  = LZ commands
    0x74  = n, n token bytes, n u16 pairs, then LZ commands; a token byte read
            from the stream stands for the two bytes of its pair (low, high)
  LZ commands (Unpack_LZ @ 0x8001D4E0), read until a 0x00 byte:
    0x7F lo hi v   repeat v (lo | hi<<8) times
    0x7E n v       repeat v n+4 times
    0x01..0x7D     copy that many literal bytes
    1LLLLDDD d     copy L+3 bytes from D<<8|d + 1 back (before block start: 0)
  batch   = 0xE0 ... (Unpack_Upload @ 0x8001E1D8): u32 record lengths, see unpack_batch

Usage:
  python tools/unpack.py out/unpacked disc/DATA.0 1 2016    # sub-archive entries
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import subarc_list  # noqa: E402
import tim2png  # noqa: E402

BLOCK = 0x2000
METHODS = {0x14, 0x20, 0x30, 0x31, 0x40, 0x70, 0x71, 0x72, 0x73, 0x74, 0xFF}


class Unsupported(Exception):
    pass


def unpack_lz(src, pos, read):
    """Run LZ commands from src[pos:]. read(pos) -> (byte, new_pos). Returns (out, pos)."""
    out = bytearray()
    while True:
        b, pos = read(pos)
        if b == 0:
            return out, pos
        if b == 0x7F:
            lo, pos = read(pos)
            hi, pos = read(pos)
            v, pos = read(pos)
            out += bytes([v]) * (lo | hi << 8)
        elif b == 0x7E:
            n, pos = read(pos)
            v, pos = read(pos)
            out += bytes([v]) * (n + 4)
        elif not b & 0x80:
            for _ in range(b):
                v, pos = read(pos)
                out.append(v)
        else:
            d, pos = read(pos)
            dist = ((b & 7) << 8 | d) + 1
            for _ in range(((b >> 3) & 15) + 3):
                out.append(out[-dist] if len(out) >= dist else 0)


def u16(src, pos):
    return src[pos] | src[pos + 1] << 8


def unpack_block(src, pos):
    """Decode one block at src[pos]. Returns (bytes, bytes consumed)."""
    method = src[pos]
    if method == 0x73:
        out, end = unpack_lz(src, pos + 1, lambda p: (src[p], p + 1))
        return bytes(out), end - pos
    if method == 0x72:  # embedded 0x73/0x74 block, then de-interleave into even/odd bytes
        n = u16(src, pos + 1)
        tmp, used = unpack_block(src, pos + 3)
        out = bytearray(n)
        half = (n + 1) // 2
        out[0::2] = tmp[:half]
        out[1::2] = tmp[half:half + n // 2]
        return bytes(out), used + 3
    if method == 0x70:  # 32-byte groups: fill byte + mask (set bit = fill, clear = literal)
        n, p, out = u16(src, pos + 1), pos + 3, bytearray()
        for _ in range(n):
            fill, mask = src[p], struct.unpack_from("<I", src, p + 1)[0]
            p += 5
            for bit in range(31, -1, -1):
                if mask >> bit & 1:
                    out.append(fill)
                else:
                    out.append(src[p])
                    p += 1
        tail = src[p]
        out += src[p + 1:p + 1 + tail]
        return bytes(out), p + 1 + tail - pos
    if method == 0x71:  # RLE: 0nnnnnnn literals | 1nnnnnnn v (repeat)
        p, out = pos + 1, bytearray()
        while src[p]:
            b = src[p]
            if b & 0x80:
                out += bytes([src[p + 1]]) * (b & 0x7F)
                p += 2
            else:
                out += src[p + 1:p + 1 + b]
                p += 1 + b
        return bytes(out), p + 1 - pos
    if method == 0x40:  # fill
        return bytes([src[pos + 1]]) * u16(src, pos + 2), 4
    if method == 0x30:  # (count u8, value) pairs, count 0 ends
        p, out = pos, bytearray()
        while src[p + 1]:
            out += bytes([src[p + 2]]) * src[p + 1]
            p += 2
        return bytes(out), p + 2 - pos
    if method == 0x31:  # (count u16, value) triples, count 0 ends
        p, out = pos, bytearray()
        while u16(src, p + 1):
            out += bytes([src[p + 3]]) * u16(src, p + 1)
            p += 3
        return bytes(out), p + 3 - pos
    if method == 0xFF:  # stored
        n = u16(src, pos + 1)
        return bytes(src[pos + 3:pos + 3 + n]), n + 3
    if method == 0x20:  # LZ with absolute (3-byte) and relative (2-byte) copies
        p, out = pos + 1, bytearray()
        while src[p]:
            b = src[p]
            if not b & 0x80:
                out += src[p + 1:p + 1 + b]
                p += 1 + b
            elif not b & 0x40:
                start = u16(src, p + 1)
                for i in range((b & 0x3F) + 3):
                    out.append(out[start + i])
                p += 3
            else:
                dist = src[p + 1] + 1
                for _ in range((b & 0x3F) + 3):
                    out.append(out[-dist])
                p += 2
        return bytes(out), p + 1 - pos
    if method == 0x14:  # 4-bit: 16-byte table, each data byte -> table[lo], table[hi]
        # UNVERIFIED: the decompiled loop and return value disagree; this follows the
        # return value (n output bytes from n/2 data bytes), which positions the next block.
        n, table = u16(src, pos + 1), src[pos + 3:pos + 19]
        out = bytearray()
        for b in src[pos + 19:pos + 19 + (n + 1) // 2]:
            out += bytes((table[b & 15], table[b >> 4]))
        return bytes(out[:n]), (n >> 1) + 0x13
    if method == 0x74:
        n = src[pos + 1]
        tokens = src[pos + 2:pos + 2 + n]
        pairs = struct.unpack_from(f"<{n}H", src, pos + 2 + n)
        expand = {t: pairs[i] for i, t in reversed(list(enumerate(tokens)))}  # first match wins
        pending = []

        def read(p):
            if pending:
                return pending.pop(), p
            b = src[p]
            if b in expand:
                pending.append(expand[b] >> 8)
                return expand[b] & 0xFF, p + 1
            return b, p + 1

        out, end = unpack_lz(src, pos + 2 + 3 * n, read)
        return bytes(out), end - pos
    raise Unsupported(f"method {method:#04x}")


def unpack_stream(src, pos=0):
    """Decode blocks until a 0x00 method byte; block k lands at k*0x2000."""
    out = bytearray()
    k = 0
    while pos < len(src) and src[pos] != 0:
        data, used = unpack_block(src, pos)
        out[k * BLOCK:] = data
        pos += used
        k += 1
        if used > BLOCK + 3:
            break
    return bytes(out)


def unpack_batch(src):
    """0xE0 container: [E0 ..][u32 len]{ [u32 size][stream (len bytes)] [u32 len] }* 0.
    len == 1 is a 'wait for GPU' marker with no payload."""
    images, pos = [], 4
    length = struct.unpack_from("<I", src, pos)[0]
    pos += 4
    while length:
        if length != 1:
            images.append(unpack_stream(src, pos + 4))
            pos += 4 + length
        length = struct.unpack_from("<I", src, pos)[0]
        pos += 4
    return images


def unpack_any(src):
    if src[:4] == b"pBAV" or not any(src[:16]):
        return []  # VAB header / VAB body, not compressed
    if src[:1] == b"\xe0":
        return unpack_batch(src)
    if src[:1] and src[0] in METHODS:
        return [unpack_stream(src)]
    return []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("pack")
    ap.add_argument("entry", type=int, nargs="+")
    args = ap.parse_args()

    data = Path(args.pack).read_bytes()
    entries = subarc_list.pack_entries(data)
    out = Path(args.out)
    stats = {"sections": 0, "unpacked": 0, "tims": 0, "unsupported": {}, "errors": 0}
    for e in args.entry:
        blob = data[entries[e][0]:entries[e][1]]
        # Compressed streams only appear as sub-archive sections. Whole entries are
        # skipped: code overlays start with an id (e.g. 0x30) that looks like a method byte.
        for i, (a, b) in enumerate(subarc_list.sections(blob) or []):
            stats["sections"] += 1
            try:
                results = unpack_any(blob[a:b])
            except Unsupported as exc:
                key = str(exc)
                stats["unsupported"][key] = stats["unsupported"].get(key, 0) + 1
                continue
            except (IndexError, struct.error):
                stats["errors"] += 1
                continue
            for j, res in enumerate(results):
                stats["unpacked"] += 1
                name = f"{e:04d}_{i:03d}" + (f"_{j:02d}" if len(results) > 1 else "")
                folder = out / f"{e:04d}"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{name}.bin").write_bytes(res)
                for off, tim in tim2png.scan(res):
                    pal = tim["clut"][0] if tim["clut"] else None
                    (folder / f"{name}_{off:05x}.png").write_bytes(tim2png.render(tim, pal))
                    stats["tims"] += 1
    print(stats)


if __name__ == "__main__":
    main()
