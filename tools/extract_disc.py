#!/usr/bin/env python3
"""Extract every file from a PS1 MODE2/2352 disc image.

Usage: python tools/extract_disc.py "Crisis Beat (Europe).bin" disc/

Files made of Mode 2 Form 1 sectors (normal data) are written as plain
2048-byte-per-sector files. Files containing Form 2 sectors (STR video,
XA audio) are written as 2336-byte sectors (subheader + payload), the
layout tools like jPSXdec and mkpsxiso expect.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

RAW = 2352
SYNC = 16  # 12 sync bytes + 4 header bytes; Mode 2 subheader follows


class Disc:
    def __init__(self, path):
        self.f = open(path, "rb")

    def raw(self, lba):
        self.f.seek(lba * RAW)
        return self.f.read(RAW)

    def user(self, lba):
        return self.raw(lba)[SYNC + 8:SYNC + 8 + 2048]

    def is_form2(self, lba):
        return bool(self.raw(lba)[SYNC + 2] & 0x20)


def walk(disc, lba, size, path, out):
    data = b"".join(disc.user(lba + i) for i in range((size + 2047) // 2048))
    i = 0
    while i < len(data):
        length = data[i]
        if length == 0:
            i = (i // 2048 + 1) * 2048
            continue
        rec = data[i:i + length]
        elba, esize = struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0]
        flags, nlen = rec[25], rec[32]
        name = rec[33:33 + nlen]
        if name not in (b"\x00", b"\x01"):
            name = name.decode("ascii").split(";")[0]
            if flags & 2:
                walk(disc, elba, esize, path + name + "/", out)
            else:
                out.append((path + name, elba, esize))
        i += length


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    disc, dest = Disc(sys.argv[1]), Path(sys.argv[2])
    pvd = disc.user(16)
    assert pvd[1:6] == b"CD001", "not an ISO9660 Mode 2 image"
    root = pvd[156:190]
    files = []
    walk(disc, struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0], "", files)

    manifest = []
    for name, lba, size in sorted(files, key=lambda f: f[1]):
        count = (size + 2047) // 2048
        form2 = any(disc.is_form2(lba + n) for n in range(count))
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha1()
        with open(target, "wb") as w:
            for n in range(count):
                if form2:
                    chunk = disc.raw(lba + n)[SYNC:SYNC + 2336]
                else:
                    chunk = disc.user(lba + n)[:min(2048, size - n * 2048)]
                w.write(chunk)
                h.update(chunk)
        manifest.append({"name": name, "lba": lba, "size": size,
                         "form2": form2, "sha1": h.hexdigest()})
        print(f"{lba:7d} {size:10d} {'XA ' if form2 else '   '} {name}")

    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
