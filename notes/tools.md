# Tool setup (Windows)

| Tool | Version | Location | How |
|---|---|---|---|
| Eclipse Temurin JDK | 21.0.12 | `C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot` | `winget install EclipseAdoptium.Temurin.21.JDK` |
| ImHex | 1.38.1 | `C:\Program Files\ImHex` | `winget install WerWolv.ImHex` |
| Ghidra | 12.1.4 | `C:\Users\Lucas\tools\ghidra_12.1.4_PUBLIC` | zip from GitHub releases (not in winget) |
| ghidra_psx_ldr | 2026.10.03 (for 12.1.4) | `<ghidra>\Ghidra\Extensions\ghidra_psx_ldr` | zip from lab313ru/ghidra_psx_ldr releases |
| PCSX-Redux | nightly 28621.20261019.19 | `C:\Users\Lucas\tools\pcsx-redux` | zip downloaded by hand, see below |

## Notes

- **ghidra_psx_ldr must match the Ghidra version exactly.** When upgrading
  Ghidra, download the plugin zip whose name contains the same version.
- **PCSX-Redux:** the winget package (`GrumpyCoders.PCSX-Redux`) has a dead
  download link. Get the Windows build from
  https://distrib.app/pub/org/pcsx-redux/project/dev-win-x64 (the page needs
  JavaScript, so use a browser) and unzip it into `C:\Users\Lucas\tools\pcsx-redux`.
  It includes OpenBIOS, a free replacement for the Sony BIOS. A BIOS dumped
  from your own console is more accurate, if games misbehave.
- **Running Ghidra:** run `ghidraRun.bat`. It finds the Temurin JDK on its own.
