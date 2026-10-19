# DATA.0 / GALLERY.0 pack format

Status: **table layout confirmed**; entry contents mostly unknown.

## Container

```
u32 offsets[N]   // little-endian byte offsets, each a multiple of 0x800
                 // offsets[0] == table size (DATA.0: 0x2000, GALLERY.0: 0x800)
                 // unused slots are 0
<entries>        // entry i = [offsets[i], offsets[i+1]); last runs to EOF
```

- DATA.0: 2037 entries, 0x1181D800 bytes. GALLERY.0: 14 entries.
- No names. The game must refer to entries by index (still to confirm in the exe).
- Offsets are byte offsets but always sector aligned, so the loader probably
  turns them into a CD sector number with `offset / 0x800`.

List or extract with `python tools/pack_list.py disc/DATA.0 [--extract out/DATA]`.

## Entry types seen (first bytes)

| Head | Count | Guess |
|---|---|---|
| `00 00 00 00 ...` (0x800 long) | ~1001 | empty / reserved slot |
| `10 00 00 00 09 00 00 00` | ~373 | **TIM image**, 8bpp with CLUT. All of GALLERY.0 |
| `00 04 00 00 20 1c ...` / `00 02 00 00 20 12 ...` | many | header of 0x400 or 0x200 bytes holding ascending u32 offsets, so probably a sub-archive |
| `70 aa 05 00 18 68 06 00` (entries 0,2,4,...,10) | few | ascending u32s. Unknown, possibly an offset table |
| `NN 00 00 00` + `0x8006xxxx` pointers / MIPS code | entries 16-21, 24 | **code overlays**: u32 id (6..12) then code/data that loads near 0x8006xxxx |
| `70 42 41 56` (`pBAV`) | entry 22 | **VAB** sound bank (PsyQ libsnd) |
| `NN 00 00 00 0a 0a 44 45...` | entry 18 | maybe text, or an overlay holding strings |

## Loader (SLES_027.93)

Names are listed in [symbols.tsv](symbols.tsv).

- `Data_Init` (0x8001E560) runs `CdSearchFile("\DATA.0;1")` and stores the LBA in
  `g_DataStartLba`. It reads the 4-sector table to 0x80100000, writes a 0 at
  0x800FFFFC, then fills `g_DataEntrySectors[i] = (off[i] - off[i-1]) >> 11`
  for i = 0..2036.
- `Data_LoadEntry(_, n, dst)` (0x8001E488) reads `g_DataEntrySectors[n+1]` sectors
  from `g_DataStartLba + off[n]/0x800`. Its entry n is the same as
  `pack_list.py`'s entry n. The first argument (always `&0x80058768`) is unused.
- `Data_SeekEntry(_, n)` (0x8001E4EC) only seeks to entry n. It is used before streaming.
- No decompression happens in the loader. Any compression would be handled by the caller.

## Known entries

| Entry | Loaded to | Caller | What |
|---|---|---|---|
| 16, 17, 19, 20, 21, 24 | `0x80064668` (`g_OverlayBase`) | FUN_800233A8 | code overlays (slot 1) |
| 0, 1 (seen) | 0x800E2000, 0x800D5000 | FUN_800245BC | always loaded together before overlay 16. Shared game data? |
| 2016 (seen) | 0x8015C000 | FUN_800248F4 | `00 02 00 00` sub-archive. Entries 2014–2035 have the same kind of header |
| odd: 105, 107, ... | 0x80154000 | FUN_80023D30 (`idx + g[0x800588AC]*2`) | scene data (head `10 00 00 00 30 xx`) |
| even: 104, 106, 108, 110, also 166 | 0x80158000 | overlay 16 @ 0x80068CAC | **scene code overlay (slot 2)**: u32 id (0x2F, 0x30, 0x31, ...; 166 = 0x11) then MIPS code |

FUN_800233A8 is probably the game-mode switch: it picks which overlay to load.
Code inside overlays also calls `Data_LoadEntry`/`Data_SeekEntry`. Overlay 16 calls them from
0x80068CAC (load) and 0x80068FE8 (seek). Overlay 20 calls `Data_SeekEntry` from 0x80065744.

## Scene layout (entries 25–2005)

Read from `Scene_LoadCode` (ovl16::80068AEC) and `Scene_LoadData` (0x80023D30):

```
data entry = base - 1 + g_SceneId * 2   -> 0x80154000
code entry = base     + g_SceneId * 2   -> 0x80158000  (u32 id, then MIPS code + embedded data)
```

`base` depends on `g_SceneGroup` (u8 at 0x8005890F):

| g_SceneGroup | base | entries | scenes present |
|---|---|---|---|
| 0, 10 | 26 | 25–223 | 85 (ids 7..98) |
| 1, 11 | 224 | 223–421 | 85 (ids 7..98) |
| 3 | 422 | 421–619 | 55 (ids 7..66) |
| 2 | 620 | 619–817 | 55 |
| 4 | 818 | 817–1015 | 55 |
| 5 | 1016 | 1015–1213 | 55 |
| 6, 12, others | 1214 | 1213–1411 | 55 |
| 8, 14 | 1412 | 1411–1609 | 55 |
| 7, 13 | 1610 | 1609–1807 | 55 |
| 9, 15 | 1808 | 1807–2005 | 55 |

The groups sit 198 entries apart (99 scene slots each). The first data slot of each
group overlaps the last code slot of the group before it.

- **Scene data is the same in every group.** Each group's copy is byte-identical
  (for example, scene 40 data has the same hash in all 10). It is duplicated on the disc,
  probably to cut seek times.
- **Scene code differs per group.** There are 413 distinct blobs, and they differ in
  embedded binary data rather than in text strings. The header id is the same across
  groups (scene 40 = 0x2F).
- What a group *means* is open. It is not a language. It is not chosen in overlay 20
  (which only reads it). It is written by `Mode_LoadOverlay` and overlay 21.
  Candidates: playable character, difficulty, or game mode.
- Session 1 ran with group 0: scene 70 -> code entry 166, scene 40 -> 105/106, scene 41 -> 107/108.

## Runtime log (first session)

Captured with `tools/pcsx/log_loads.lua`. The times are emulated seconds since boot.
The screens were confirmed by playing.

| Time | Loads | Screen |
|---|---|---|
| 17.9 | overlay 21 | boot: logos and FMV |
| 65.5 | overlay 17 (0x1800 bytes) | title / menu |
| 76–84 | 1, 0, overlay 16, 2016, seek 29, scene code 166 | first in-game scene, before the first playable area (demo or intro: not yet told apart) |
| 89–95 | 1, 0, overlay 20, seek 16 | a screen that is not gameplay, between that scene and the first area |
| 103–106 | overlay 16, scene 105 + 106 | gameplay, first area |
| 205–213 | seek 107, scene 107 + 108 | gameplay, next area |

## Overlays (slot 1, 0x80064668)

| Entry | Size | Role |
|---|---|---|
| 21 | 0xCB000 | boot: logos and FMV. Large, and it writes g_SceneGroup, so it probably holds menus too |
| 17 | 0x1800 | title / menu |
| 16 | 0x6E000 | **in-game engine**: loads the scene pairs into slot 2 |
| 20 | 0x5B000 | screen that is not gameplay, shown before the first area |
| 19, 24 | | not seen yet |

Seeks prefetch: `seek 16` came about 8 s before `load 16`. `seek 29` targets an empty
slot, which probably just parks the drive head.

## Open questions

- [ ] Overlay header: the first u32 is a small number (6..12), followed by what look
      like function pointers into the overlay. Is it an export table the exe calls through?
- [ ] Load overlays into Ghidra as overlay blocks at 0x80064668 (they overlap each other).
- [ ] Work out what FUN_800245BC / FUN_800248F4 / FUN_80023D30 load (index math).
- [ ] Find the meaning of the `0x400`/`0x200` sub-archive headers.
- [ ] Find out what entries 18, 22 (VAB) and 23 (TIM) are. No direct `Data_LoadEntry` call uses them.
