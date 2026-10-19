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

## Layout

| Path | Contents |
|---|---|
| `tools/` | Python scripts (standard library only) |
| `notes/` | Findings: [disc & exe](notes/disc.md), [DATA.0 format](notes/data0.md) |
| `tools/ghidra_scripts/` | Ghidra scripts: export functions, decompile xrefs, create functions, apply `notes/symbols.tsv` |
| `disc/`, `out/`, `ghidra/` | Local, git-ignored (`ghidra/CrisisBeat.gpr` is the Ghidra project) |

## Runtime logging (PCSX-Redux)

[tools/pcsx/log_loads.lua](tools/pcsx/log_loads.lua) logs every DATA.0 load and seek to `out/loads.tsv`.
Run it from the repo root:

```
pcsx-redux.exe -iso "Crisis Beat (Europe).cue" -debugger -interpreter -run -dofile tools\pcsx\log_loads.lua
```

## Ghidra workflow

Names live in [notes/symbols.tsv](notes/symbols.tsv), so they are kept in git and can be reviewed.
Add names there, then apply them to the project (close the Ghidra window first):

```
<ghidra>\support\analyzeHeadless.bat ghidra CrisisBeat -process SLES_027.93 -noanalysis ^
    -scriptPath tools\ghidra_scripts -postScript ApplySymbols.java notes\symbols.tsv
```

Or run `ApplySymbols.java` from Ghidra's Script Manager (category *CrisisBeat*).

## External tools

- **Ghidra** + [ghidra_psx_ldr](https://github.com/lab313ru/ghidra_psx_ldr): static analysis of `disc/SLES_027.93`
- **PCSX-Redux**: emulator and debugger
- **ImHex**: hex editor and format patterns
- **jPSXdec**: STR video / XA audio
