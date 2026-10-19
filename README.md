# Crisis Beat reverse engineering

Research into *Crisis Beat* (PlayStation, Europe, SLES-02793): how it works,
its file formats, and tools to extract its assets.

This repo contains **no game data**. Use your own legally dumped disc image.

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

## Layout

| Path | Contents |
|---|---|
| `tools/` | Python scripts (standard library only) |
| `notes/` | Findings: [disc & exe](notes/disc.md), [DATA.0 format](notes/data0.md), [asset formats](notes/formats.md) |
| `tools/ghidra_scripts/` | Ghidra scripts: export functions, decompile functions / xrefs, create functions, load overlays, apply `notes/symbols.tsv` |
| `disc/`, `out/`, `ghidra/` | Local, git-ignored (`ghidra/CrisisBeat.gpr` is the Ghidra project) |

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
