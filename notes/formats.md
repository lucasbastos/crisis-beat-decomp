# Asset formats

## Sub-archives (inside DATA.0 entries)

Same layout as DATA.0: ascending u32 offsets, the first one = table size, with unused
slots zeroed. Each section runs to the next offset. List them with `tools/subarc_list.py`.

| Table size | Where | Example |
|---|---|---|
| 0x10 | scene data (odd scene entries) | entry 105: 2× VAB header + 2× VAB body |
| 0x200 | story-scene banks 2014–2035 | entry 2016: VAB header, VAB body, `74 0a 0e 1b…` block, `73 01…` block |
| 0x400 | per-scenario data (odd entries 1, 3, …) | entry 1: 157 sections |

Entry 0 (even per-scenario entries) is **not** a sub-archive. Its head (`70 aa 05 00 18 68 06 00`)
is two ascending values, not a table that starts with its own size.

## Section kinds seen

| Head | Guess |
|---|---|
| `70 42 41 56` (`pBAV`) | VAB sound-bank header (.VH, PsyQ libsnd) |
| 16+ zero bytes | VAB body (.VB ADPCM samples start with a zero block) |
| `73 …`, `74 …`, or another method byte | **compressed TIM** (see Compression below) |
| `04 00 02 00 3c 00 00 00 …` | small tables, maybe sprite / animation layout |

## TIM images

Only **11 standard TIMs** exist in DATA.0 (found by `tools/tim2png.py --all-entries`):

- entry 21 (overlay 21, title / menus): 3 TIMs embedded in the overlay
  (608×160 twice, 320×240), all 8bpp.
- entry 23: 8 TIMs, 8bpp, 96–212 px wide. They are not loaded by `Data_LoadEntry` directly.

GALLERY.0 is 13 full-screen 8bpp TIMs (304–640 px wide). Convert them with `--opaque`.

Most of the game's art is compressed (next section).

## Compression

Reimplemented in [tools/unpack.py](../tools/unpack.py) from the exe (names in symbols.tsv).
`Unpack_Upload` (0x8001E1D8) takes a list of streams, unpacks each into a work buffer
(0x801F0000), and uploads the resulting TIM to VRAM with `Tim_Upload`.

```
stream = block* 0x00     block k is written at dst + k*0x2000 (at most 0x2000 bytes out)
batch  = 0xE0 xx xx xx, u32 len, { u32 size, stream (len bytes), u32 len }*; len 0 ends, len 1 = GPU sync
```

| Method | Handler | Meaning |
|---|---|---|
| 0x73 | Unpack_LZ | LZ commands (below) |
| 0x74 | Unpack_LZ | n, n token bytes, n u16 pairs, then LZ; a token byte stands for (pair low, pair high) |
| 0x72 | Unpack_Interleave72 | u16 n, embedded 0x73/0x74 block; first ceil(n/2) bytes go to even offsets, the rest to odd |
| 0x70 | Unpack_Mask70 | u16 groups; per group: fill byte, u32 mask (MSB first: 1 = fill, 0 = next literal); then u8 tail + tail literals |
| 0x71 | Unpack_RLE71 | `0nnnnnnn` + n literals, `1nnnnnnn v` = repeat; 0 ends |
| 0x40 | Unpack_Fill40 | v, u16 count |
| 0x30 / 0x31 | Unpack_RLE30 / 31 | (u8 / u16 count, value) ..., count 0 ends |
| 0x20 | Unpack_LZ20 | `0nnnnnnn` literals, `10LLLLLL lo hi` copy from block offset, `11LLLLLL d` copy from d+1 back; length L+3 |
| 0x14 | Unpack_Nibble14 | 16-byte table + 4-bit indices (**unverified**, not used in DATA.0) |
| 0xFF | Unpack_Stored | u16 n + n raw bytes |

LZ commands (0x73 / 0x74), read until a 0x00 byte:

| Bytes | Meaning |
|---|---|
| `7F lo hi v` | repeat v (lo + hi*256) times |
| `7E n v` | repeat v n+4 times |
| `01`..`7D` | that many literal bytes |
| `1LLLLDDD d` | copy L+3 bytes from DDD*256+d+1 back; reads before the block start give 0 |

## Area-code entries (even scene entries)

Gameplay scene-code entries (for example 104, 106, 108, 110, 284, 290) are **0x4000 bytes of
code followed by a resource block**. Story scenes (for example 166, 372) have no block;
their images come from the scene banks.

```
0x0000  u32 id, MIPS code                    (loaded at 0x80158000)
0x4000  u32 offsets[16]                      relative to 0x4000, ascending
0x4040  section 0 .. offsets[0]              section i = [offsets[i-1], offsets[i])
```

Section layout is the same in every area (sizes vary):

| Section | Typical size | Head | What |
|---|---|---|---|
| 0 | 0x1A000–0x32000 | method byte | **area textures**: compressed TIM streams back to back, each 4-byte aligned (zero padding) |
| 1 | 0x1EC–0x3F4 | `40 00 00 00` | small table |
| 2 | 8 | offset | ? |
| 3, 4 | up to 0x42000 | `e5 e5 e5 e5` | large structures; entry 0 uses the same marker. Map / geometry? |
| 5–7 | 0x3000–0x11000 | zeros | ? |
| 8–15 | small | offsets / zeros | tables |

How the area code finds the block is not traced yet: it never calls `Unpack_Upload`
directly, and there are no absolute pointers to the streams.

## Coverage

`tools/unpack.py` over all 2037 entries decodes **79,581 streams in 405 entries, every one a
valid TIM, with no errors**. Only **4,300 are unique** (28 MB as PNG): 3,942 first seen in area
resource blocks and 358 in team data (entries 1–15). Every scene-bank image (2005–2035)
also appears in the team data. Area textures repeat across the 10 scenario groups.
Scene data entries (odd entries 25–2005) hold only VABs.

## Open questions

- [x] Find the decompressor (`Unpack_Upload` and friends, see Compression).
- [x] Where are the area graphics? Section 0 of each area-code entry's resource block.
- [ ] How does the area code reach the resource block (and Unpack_Upload)? Trace it at
      runtime with a breakpoint on Unpack_Stream (0x8001DE94).
- [ ] The `e5 e5 e5 e5` structures (area sections 3/4, entry 0): maps or geometry?
- [ ] Find the format of the `04 00 02 00` tables (sprite / animation layout?).
- [ ] Entry 0 / 2 (even per-scenario entries): find their format.
