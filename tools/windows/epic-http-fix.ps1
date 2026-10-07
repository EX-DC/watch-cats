<#
.SYNOPSIS
  Makes Epic Games Launcher prefer plain-HTTP CDNs so a LanCache server can cache its downloads.

.DESCRIPTION
  Adds  [Launcher] ForceNonSslCdn=true  to Epic's Engine.ini (in both the "Windows" and
  "WindowsEditor" config folders, because it is not certain which one the launcher reads).
  Existing files are backed up first. Run with -Revert to undo.
  Run once per Windows PC. Close Epic Games Launcher completely (also from the system tray) first.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\epic-http-fix.ps1
  powershell -ExecutionPolicy Bypass -File .\epic-http-fix.ps1 -Revert
#>
[CmdletBinding()]
param([switch]$Revert)

$ErrorActionPreference = 'Stop'
$Section = 'Launcher'
$Key = 'ForceNonSslCdn'
$base = Join-Path $env:LOCALAPPDATA 'EpicGamesLauncher\Saved\Config'

function Set-IniValue([string]$Path, [string]$Section, [string]$Key, [string]$Value) {
    $lines = @()
    if (Test-Path -LiteralPath $Path) { $lines = @(Get-Content -LiteralPath $Path) }
    $out = New-Object System.Collections.Generic.List[string]
    $inSec = $false; $seen = $false; $done = $false
    foreach ($l in $lines) {
        if ($l -match '^\s*\[(.+)\]\s*$') {
            if ($inSec -and -not $done) { $out.Add("$Key=$Value"); $done = $true }
            $inSec = ($Matches[1] -ieq $Section)
            if ($inSec) { $seen = $true }
            $out.Add($l); continue
        }
        if ($inSec -and $l -match ('^\s*' + [regex]::Escape($Key) + '\s*=')) {
            if (-not $done) { $out.Add("$Key=$Value"); $done = $true }
            continue
        }
        $out.Add($l)
    }
    if ($inSec -and -not $done) { $out.Add("$Key=$Value"); $done = $true }
    if (-not $seen) {
        if ($out.Count -gt 0 -and $out[$out.Count - 1] -ne '') { $out.Add('') }
        $out.Add("[$Section]"); $out.Add("$Key=$Value")
    }
    Set-Content -LiteralPath $Path -Value $out -Encoding ASCII
}

function Show-Notice([string]$Text) {
    Write-Host ''
    Write-Host $Text -ForegroundColor Green
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show($Text, 'Watch Cats')
    } catch { }
}

if (Get-Process -Name 'EpicGamesLauncher' -ErrorAction SilentlyContinue) {
    Write-Warning 'Epic Games Launcher is running. Close it completely (also from the system tray) and run this script again.'
    exit 1
}

foreach ($folder in 'Windows', 'WindowsEditor') {
    $dir = Join-Path $base $folder
    $ini = Join-Path $dir 'Engine.ini'
    $bak = "$ini.watchcats.bak"
    $created = "$ini.watchcats.created"

    if ($Revert) {
        if (Test-Path -LiteralPath $created) {
            Remove-Item -LiteralPath $ini, $created -Force -ErrorAction SilentlyContinue
            Write-Host "Removed $ini"
        } elseif (Test-Path -LiteralPath $bak) {
            Move-Item -LiteralPath $bak -Destination $ini -Force
            Write-Host "Restored $ini"
        }
        continue
    }

    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    if (Test-Path -LiteralPath $ini) {
        if (-not (Test-Path -LiteralPath $bak)) { Copy-Item -LiteralPath $ini -Destination $bak }
    } else {
        New-Item -ItemType File -Path $created -Force | Out-Null
    }
    Set-IniValue -Path $ini -Section $Section -Key $Key -Value 'true'
    Write-Host "Updated $ini"
}

if ($Revert) { Show-Notice 'Watch Cats: Epic setting reverted. Restart Epic Games Launcher.' }
else { Show-Notice 'Watch Cats: done. Start Epic Games Launcher and download a game; it should now use LanCache over HTTP.' }
