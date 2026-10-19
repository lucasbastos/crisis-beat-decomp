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
| `73 01 10 87 ff 01 …` | **compressed data**, probably graphics. 68 of entry 1's 157 sections |
| `74 0a 0e 1b 1d 3d …` | unknown; ascending bytes, maybe a decode table |
| `04 00 02 00 3c 00 00 00 …` | small tables, maybe sprite / animation layout |

## TIM images

Only **11 standard TIMs** exist in DATA.0 (found by `tools/tim2png.py --all-entries`):

- entry 21 (overlay 21, title / menus): 3 TIMs embedded in the overlay
  (608×160 twice, 320×240), all 8bpp.
- entry 23: 8 TIMs, 8bpp, 96–212 px wide. They are not loaded by `Data_LoadEntry` directly.

GALLERY.0 is 13 full-screen 8bpp TIMs (304–640 px wide). Convert them with `--opaque`.

Most of the game's art must be in the compressed `73 01…` sections.

## Open questions

- [ ] Find the decompressor. Start from the PsyQ `LoadImage` callers in Ghidra, then
      work back to the code that reads sections out of 0x800D5000 / 0x8015C000.
- [ ] Find the format of the `04 00 02 00` tables and the `74 0a…` block.
- [ ] Entry 0 / 2 (even per-scenario entries): find their format.
