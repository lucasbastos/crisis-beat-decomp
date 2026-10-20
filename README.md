# Crisis Beat reverse engineering

Research into *Crisis Beat* (PlayStation, Europe, SLES-02793): how it works,
its file formats, and tools to extract its assets.

This repo contains **no game data**. Use your own legally dumped disc image.

## Progress

<!-- progress:start -->
Status as of 2026-10-20 14:23 UTC (after commit `8fde943`). Updated on every commit by `tools/hooks/pre-commit`; full charts on the [progress dashboard](https://claude.ai/artifact/HJouFMXmC3fZy2iSKUEBcX) (private until shared).

| Measure | Now |
|---|---|
| DATA.0 bytes understood | **48.2%** (134.9 MB of 280.1 MB) |
| DATA.0 bytes decoded to files | 18.5% (51.8 MB) |
| Entries mapped | 2,021 of 2,037 |
| Unique images extracted | 4,311 (79,592 with copies) |
| Functions named | 1,039 of 1,563 (42 by us) |
| Formats understood | 16 of 24 (4 partly) |
| Questions answered | 8 of 16 |
| Biggest unknown | Area code + resources: 134.7 MB |
<!-- progress:end -->

## Setup

1. Put `Crisis Beat (Europe).bin` / `.cue` in the repo root (git ignores them).
   Expected SHA-1 of the .bin: `f41ce71b1285648dd521979cb13c6d38a5df12bc`.
2. Extract the disc:
   ```
   python tools/extract_disc.py "Crisis Beat (Europe).bin" disc
   ```
3. List or extract pack entries:
   ```
   python tools/pack_list.py disc/DATA.0
   python tools/pack_list.py disc/DATA.0 --extract out/DATA
   ```
4. List sub-archive sections, or convert TIM images to PNG:
   ```
   python tools/subarc_list.py disc/DATA.0 1 105 2016
   python tools/tim2png.py --opaque out/tims/gallery disc/GALLERY.0
   python tools/tim2png.py out/tims/data disc/DATA.0 --all-entries
   ```
5. Decompress the packed graphics to `.bin` + `.png`, with `index.tsv` listing every copy:
   ```
   python tools/unpack.py out/assets disc/DATA.0 1 3 106 2016   # chosen entries
   ```
   Pass every entry number (0–2036) to unpack everything: 4,300 unique images
   (79,581 with duplicates), about 20 seconds. Add `--keep-duplicates` to write every copy.

## Layout

| Path | Contents |
|---|---|
| `tools/` | Python scripts (standard library only) |
| `notes/` | Findings: [disc & exe](notes/disc.md), [DATA.0 format](notes/data0.md), [asset formats](notes/formats.md) |
| `tools/ghidra_scripts/` | Ghidra scripts: export functions, decompile functions / xrefs, create functions, load overlays, apply `notes/symbols.tsv` |
| `disc/`, `out/`, `ghidra/` | Local, git-ignored (`ghidra/CrisisBeat.gpr` is the Ghidra project) |

## Progress dashboard

[tools/progress.py](tools/progress.py) measures how much of DATA.0, the executable and the
formats is worked out, and writes the dashboard's data files (statistics only, no game data):

```
python tools/progress.py out/progress
```

Add `--readme README.md` to also rewrite the status block under **Progress** above.
The git hook [tools/hooks/pre-commit](tools/hooks/pre-commit) does exactly that on every commit
and stages README.md with it (about 10 seconds; it never blocks a commit). Enable it once per clone:

```
git config core.hooksPath tools/hooks
```

Set `CB_SKIP_PROGRESS=1` to skip it for one commit.

Notes:
- Function counts come from `out/functions.tsv`. Re-export it from Ghidra (`ExportFunctions.java`)
  after naming functions, or the README and dashboard show the last export.
- The formats list inside the script is kept by hand: update it when a format is worked out.
- The dashboard itself can only be uploaded by Claude. Commits Claude makes are followed by an
  upload; after your own commits, ask Claude to refresh the dashboard.

## Runtime logging (PCSX-Redux)

[tools/pcsx/log_loads.lua](tools/pcsx/log_loads.lua) logs every DATA.0 load and seek, with the
current `g_SceneId` and `g_Scenario`, plus every write to `g_Scenario`. Each run writes its
own `out/loads-<date>-<time>.tsv`. Start it with:

```
powershell -File tools\pcsx\run.ps1
```

The emulator process is `pcsx-redux.main` (`pcsx-redux.exe` only launches it).

## Ghidra workflow

Names live in [notes/symbols.tsv](notes/symbols.tsv), so they are kept in git and can be reviewed.
Add names there, then apply them to the project (close the Ghidra window first):

```
<ghidra>\support\analyzeHeadless.bat ghidra CrisisBeat -process SLES_027.93 -noanalysis ^
    -scriptPath tools\ghidra_scripts -postScript ApplySymbols.java notes\symbols.tsv
```

Or run `ApplySymbols.java` from Ghidra's Script Manager (category *CrisisBeat*).

Overlay 16 (in-game engine) is loaded as block `ovl16`. To load another overlay, use
`ovl16` as the model; entry points are listed in [notes/data0.md](notes/data0.md):

```
python tools/pack_list.py disc/DATA.0 --entry 21 --extract out/DATA
<ghidra>\support\analyzeHeadless.bat ghidra CrisisBeat -process SLES_027.93 -noanalysis ^
    -scriptPath tools\ghidra_scripts -postScript LoadOverlay.java out\DATA\0021.bin 80064668 ovl21 80065ffc
```

## External tools

- **Ghidra** + [ghidra_psx_ldr](https://github.com/lab313ru/ghidra_psx_ldr): static analysis of `disc/SLES_027.93`
- **PCSX-Redux**: emulator and debugger
- **ImHex**: hex editor and format patterns
- **jPSXdec**: STR video / XA audio
