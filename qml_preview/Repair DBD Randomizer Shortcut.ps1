# Repair the current user's DBD Randomizer shortcut without touching other links.
# Explicitly run from the extracted RC portable directory (no administrator needed).
param(
    [string]$InstallDir = $PSScriptRoot,
    [string]$ShortcutDirectory = ""
)
$ErrorActionPreference = "Stop"
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$exe = Join-Path $InstallDir "DBDRandomizerQtBeta.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "DBD Randomizer Qt EXE not found in $InstallDir. Run this file from the extracted RC folder."
}
if ([string]::IsNullOrWhiteSpace($ShortcutDirectory)) {
    $ShortcutDirectory = [Environment]::GetFolderPath("DesktopDirectory")
}
if (-not (Test-Path -LiteralPath $ShortcutDirectory -PathType Container)) {
    throw "Desktop/shortcut directory not found: $ShortcutDirectory"
}
$shell = New-Object -ComObject WScript.Shell
$destinations = @((Join-Path $ShortcutDirectory "DBD Randomizer.lnk"))
# An existing per-user Start Menu link is safe to refresh, but do not create one
# unrequested or modify the system-wide Start Menu.
if ($PSScriptRoot -and -not $PSBoundParameters.ContainsKey("ShortcutDirectory")) {
    $start = [Environment]::GetFolderPath("Programs")
    if (-not [string]::IsNullOrWhiteSpace($start)) {
        $menuLink = Join-Path $start "DBD Randomizer.lnk"
        if (Test-Path -LiteralPath $menuLink -PathType Leaf) {
            $destinations += $menuLink
        }
    }
}
foreach ($file in $destinations) {
    $shortcut = $shell.CreateShortcut($file)
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.IconLocation = "$exe,0"
    $shortcut.Description = "DBD Ultimate Search Randomizer - Qt Release Candidate"
    $shortcut.Arguments = ""
    $shortcut.Save()
    Write-Output ("Shortcut updated: " + $file)
}
