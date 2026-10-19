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
| 16, 17, 19, 20, 21, 24 | `0x80064668` (`g_OverlayBase`) | Mode_LoadOverlay | code overlays (slot 1) |
| 2s+1, 2s (s = g_Scenario; 0–15 = 8 pairs) | 0x800D5000, 0x800E2000 | Scenario_LoadCommonData | **per-scenario data**, loaded before every in-game section. Seen: s=0 -> 1, 0; s=1 -> 3, 2 |
| 2016–2031 | 0x8015C000 | Scene_LoadBank (0x800248F4) | **per-story-scene bank** (`00 02 00 00` sub-archive). Picked by a switch on the scene number: scenes 69–98 map to 2016–2031, anything else to 2019 |
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

`base` depends on `g_Scenario` (u8 at 0x8005890F):

| g_Scenario | base | entries | scenes present |
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
- **A group is a scenario (team), not a character** (sessions 2–3). There are 4 playable
  characters in two teams, and the 2-player select offers exactly these two pairs:

  | g_Scenario | Team | Set by (overlay 21 store) |
  |---|---|---|
  | 0 | Eiji Garland + Julia Jefferson | ovl21::800683A0 (Julia), ovl21::800689A8 (2P) |
  | 1 | Kenneth Kirova + Yan H Feisu | ovl21::800683C4 (Kenneth, Yan) |

- **The character only picks the intro scene:** Eiji 70, Julia 72, Kenneth 74, Yan 67.
  After the intro, both members of a team play the same areas (team 0 starts at scene 40,
  team 1 at scene 30).
- **Scenes 67–98 look like story cutscenes.** They exist only in groups 0 and 1, include
  every character intro, and each has its own bank (Scene_LoadBank). Groups 2–9 stop
  at scene 66, so they hold gameplay areas but no story. What selects them (another
  mode? difficulty?) is open.
- Before an intro, the game seeks to `base + 3`: entry 29 for team 0, 227 for team 1.

| Run | g_Scenario | Intro scene -> code entry | Bank | First area |
|---|---|---|---|---|
| Eiji (session 1) | 0 | 70 -> 166 | 2016 | 40 -> 105/106, then 41 |
| Julia (session 3) | 0 | 72 -> 170 | 2017 | 40 |
| Kenneth (session 2) | 1 | 74 -> 372 | 2018 | 30 -> 283/284, then 33, 34 |
| Yan (session 3) | 1 | 67 -> 358 | 2019 | 30, then 33 |
| 2P Eiji + Julia (session 3) | 0 | 70 -> 166 | 2016 | 40 |
| Attract demo | 0 | 7 -> 40 (no intro) | none | |

## Runtime logs

Captured with `tools/pcsx/log_loads.lua`. The times are emulated seconds since boot.

### Session 1: Eiji (g_Scenario 0)

| Time | Loads | Screen |
|---|---|---|
| 17.9 | overlay 21 | boot, title, menus, character select |
| 65.5 | overlay 17 (0x1800 bytes) | short cutscene after the character is chosen |
| 76–84 | 1, 0, overlay 16, 2016, seek 29, scene code 166 | first in-game scene, before the first playable area (demo or intro: not yet told apart) |
| 89–95 | 1, 0, overlay 20, seek 16 | a screen that is not gameplay, between that scene and the first area |
| 103–106 | overlay 16, scene 105 + 106 | gameplay, first area |
| 205–213 | seek 107, scene 107 + 108 | gameplay, next area |

### Session 2: Kenneth (g_Scenario 1)

| Time | Loads | Screen |
|---|---|---|
| 18.0 | overlay 21 | boot / title |
| 133–139 | Mode_LoadOverlay sets scenario 0; 1, 0, overlay 16, scene 7 (39/40) | attract demo (left idle on the title screen) |
| 174.3 | overlay 21 | back to title |
| 227.3 | ovl21::800683C4 writes g_Scenario = 1 | **Kenneth picked** |
| 230.3 | overlay 17 | short cutscene after selection |
| 238–245 | 3, 2, overlay 16, 2018, seek 227, scene code 372 (scene 74) | Kenneth's intro |
| 252–258 | 3, 2, overlay 20, seek 16 | screen that is not gameplay |
| 266–268 | overlay 16, scene 30 (283/284) | gameplay |
| 345–352 | seek 289, scene 33 (289/290) | next area |
| 455–460 | seek 291, scene 34 (291/292) | next area |

## Overlays (slot 1, 0x80064668)

| Entry | Size | Role |
|---|---|---|
| 21 | 0xCB000 | boot, title, menus, **character select** (writes g_Scenario). Entry ovl21::80065FFC |
| 17 | 0x1800 | short cutscene after character select. Entry 0x80065764(mode) |
| 16 | 0x6E000 | **in-game engine**: loads the scene pairs into slot 2 |
| 20 | 0x5B000 | screen that is not gameplay, shown before the first area |
| 19, 24 | | not seen yet |

Seeks prefetch: `seek 16` came about 8 s before `load 16`. `seek 29` targets an empty
slot, which probably just parks the drive head.

## Open questions

- [ ] Overlay header: the first u32 is a small number (6..12), followed by what look
      like function pointers into the overlay. Is it an export table the exe calls through?
- [x] Load overlays into Ghidra as overlay blocks at 0x80064668 (ovl16 done, see `LoadOverlay.java`).
- [x] Work out the index math of the scene loaders (see Scene layout).
- [ ] Groups 2–9 (55 scenes, no story scenes): what selects them? Another mode or difficulty?
- [x] The 0x8015C000 bank index is picked per scene by Scene_LoadBank.
- [x] Overlay 17 is the short cutscene after character select.
- [ ] Find the meaning of the `0x400`/`0x200` sub-archive headers.
- [ ] Find out what entries 18, 22 (VAB) and 23 (TIM) are. No direct `Data_LoadEntry` call uses them.
