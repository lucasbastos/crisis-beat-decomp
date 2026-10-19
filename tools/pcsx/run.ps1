# Start PCSX-Redux on the game with the DATA.0 load logger.
# Usage (from anywhere): powershell -File tools\pcsx\run.ps1
# Each run writes its own log: out\loads-<date>-<time>.tsv
param([string]$Emulator = "$env:USERPROFILE\tools\pcsx-redux\pcsx-redux.exe")
$repo = Resolve-Path "$PSScriptRoot\..\.."
New-Item -ItemType Directory -Force "$repo\out" | Out-Null
Start-Process -FilePath $Emulator -WorkingDirectory $repo -ArgumentList @(
    '-iso', "`"$repo\Crisis Beat (Europe).cue`"",
    '-debugger', '-interpreter', '-run',
    '-dofile', "`"$repo\tools\pcsx\log_loads.lua`"")
