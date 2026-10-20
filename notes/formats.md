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
0x4000  u32 list[16]                         resource block, lands at 0x8015C000
0x4040  data and lists                       all offsets relative to 0x4000
```

**The block is 16 offset lists, not 16 sections.** `list[k]` is the offset of list k. A
list is u32 offsets (0 = unused slot) ending in **0xE5E5E5E5**. Lists of s16 records end
in 0xE5E5. The game turns each offset into a pointer in place (adds 0x8015C000). Data
can sit anywhere in the block, so the gaps between `list[k]` values are not section
sizes. The "e5 e5 e5 e5 structures" were list terminators. In a story scene, the
scene bank (Scene_LoadBank) is loaded to 0x8015C000 instead and uses the same scheme.

Overlay 16 has one setup function per list (names in symbols.tsv):

| List | Consumer | Contents (entry 106) |
|---|---|---|
| 0 | Res_LoadTextures | **compressed TIMs** (209), each sent to `Unpack_Upload` |
| 1 | Res_SetupList1 | one list of 10-byte records (5 x s16, ends 0xE5E5), passed to two placement-like functions |
| 2 / 3 | Res_LoadSoundBanks | **VAB bodies / headers**, opened in pairs by `Sound_OpenVab` (`SsVabOpenHead` + `SsVabTransBody`). Empty in 106 |
| 4 / 6 | Res_RelocateObject(id) | 194-entry tables indexed by object type; each entry is itself a list, relocated on first use |
| 5, 9, 10, 15 | several (5+10 used together in three functions) | 264-entry tables indexed by an id, mostly empty |
| 7, 8, 11 | Res_SetupList7 / 8 / 11 | single pointer each |
| 13 | Res_SetupList13 | probably the texture-animation table (next to TexAnim_Update) |

About 100 MB of each area's data is not pointed to by any list directly. It is reached
through nested lists (for example, list 4's descriptors around 0x5A200 in entry 106 point
into a region of 4-byte records that count upward, likely sprite frame tables).

## Coverage

`tools/unpack.py` over all 2037 entries decodes **79,581 streams in 405 entries, every one a
valid TIM, with no errors**. Only **4,300 are unique** (28 MB as PNG): 3,942 first seen in area
resource blocks and 358 in team data (entries 1–15). Every scene-bank image (2005–2035)
also appears in the team data. Area textures repeat across the 10 scenario groups.
Scene data entries (odd entries 25–2005) hold only VABs.

## Open questions

- [x] Find the decompressor (`Unpack_Upload` and friends, see Compression).
- [x] Where are the area graphics? Section 0 of each area-code entry's resource block.
- [x] How does the game reach the resource block? Overlay 16 reads the 16 lists at
      0x8015C000 (Res_* functions); textures go through Res_LoadTextures -> Unpack_Upload.
- [x] The `e5 e5 e5 e5` "structures": end-of-list markers.
- [ ] Formats behind lists 4/6 (per-object resources) and the 4-byte frame records.
- [ ] What lists 1, 5, 7–15 hold (read their Res_SetupList* consumers).
- [ ] Find the format of the `04 00 02 00` tables (sprite / animation layout?).
- [ ] Entry 0 / 2 (even per-scenario entries): find their format.
