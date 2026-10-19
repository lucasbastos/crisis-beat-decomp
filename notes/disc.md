# Disc and executable

Image: `Crisis Beat (Europe).bin`, a single MODE2/2352 track.
SHA-1 `f41ce71b1285648dd521979cb13c6d38a5df12bc`.

## Files

| LBA | File | Notes |
|---|---|---|
| 23 | DATA.0 | main asset pack, see [data0.md](data0.md) |
| 143442 | GALLERY.0 | 13 TIM images (same pack format) |
| 144456 | SLES_027.93 | main executable |
| 144603 | SYSTEM.CNF | `BOOT = cdrom:\SLES_027.93;1`, TCB 4, EVENT 16, STACK 0x801FFF00 |
| 144605+ | MOVIE/*.STR | FMV (Form 2, use jPSXdec) |
| 215965+ | XA/MIX*.XA | streamed music (Form 2, interleaved) |
| 287997 | SILENCE.WAV | 32 MB, probably padding |

`python tools/extract_disc.py "Crisis Beat (Europe).bin" disc/` extracts everything
and writes `disc/manifest.json` with LBAs and hashes.

## SLES_027.93

- SHA-1 `c806029a3871f14380b5c3dcac3ac0162da09177`
- PS-X EXE, load address `0x80010000`, text size `0x49000` (ends `0x80059000`)
- Entry point `0x8002CB58`; gp 0; initial sp `0x801FFFF0`
- PsyQ library tags: `bios.c` 1.86 (1997-03-28), `intr.c` 1.75 (1997-02-07),
  `sys.c` 1.140 (1998-01-12), so the SDK is about version 4.2–4.3
- Code overlays from DATA.0 load above the exe, around `0x8006xxxx`
