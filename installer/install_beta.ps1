param(
    [switch]$CreateStartupShortcut,
    [switch]$CreateDesktopShortcut = $true
)

$ErrorActionPreference = "Stop"

$AppName = "EffectPalette"
$DisplayName = "Effect Palette"
$SourceDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CepExtensionsDir = Join-Path $env:APPDATA "Adobe\CEP\extensions"
$InstallDir = Join-Path $CepExtensionsDir $AppName
$PythonLauncher = "py"
$RuntimeDataFiles = @(
    "current_selection.json",
    "premiere_cmd.json",
    "premiere_diagnose.txt",
    "premiere_effects.json",
    "premiere_favorites.json",
    "premiere_host_info.json",
    "premiere_presets.json",
    "premiere_project_items.json",
    "premiere_sequences.json",
    "worker.log"
)

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function New-Shortcut($Path, $Target, $Arguments, $WorkingDirectory, $Description) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $Target
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.Description = $Description
    $shortcut.Save()
}

function Test-IsSamePath($A, $B) {
    $resolvedA = [System.IO.Path]::GetFullPath($A).TrimEnd('\')
    $resolvedB = [System.IO.Path]::GetFullPath($B).TrimEnd('\')
    return [String]::Equals($resolvedA, $resolvedB, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-ShouldSkipCopy($Item) {
    $relative = $Item.FullName.Substring($SourceDir.Length).TrimStart('\')
    $parts = $relative -split "\\"

    if ($parts.Length -eq 0) {
        return $false
    }

    if ($parts[0] -in @(".git", "__pycache__", ".venv")) {
        return $true
    }

    if ($relative -like "*.pyc" -or $relative -like "*.pyo" -or $relative -like "*.tmp") {
        return $true
    }

    if ($relative -eq ".debug") {
        return $true
    }

    if ($parts[0] -eq "data" -and $parts.Length -eq 2 -and $parts[1] -in $RuntimeDataFiles) {
        return $true
    }

    if ($parts[0] -eq "template_project" -and ($relative -like "*.prin" -or $relative -like "*Adobe Premiere Pro Auto-Save*")) {
        return $true
    }

    return $false
}

Write-Step "Installing $DisplayName"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

if (Test-IsSamePath $SourceDir $InstallDir) {
    Write-Step "Source is already the CEP extension folder; keeping files in place"
} else {
    Write-Step "Copying extension files"
    Get-ChildItem -LiteralPath $SourceDir -Force -Recurse | ForEach-Object {
        if (Test-ShouldSkipCopy $_) {
            return
        }

        $relative = $_.FullName.Substring($SourceDir.Length).TrimStart('\')
        $target = Join-Path $InstallDir $relative

        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Force -Path $target | Out-Null
        } else {
            $targetParent = Split-Path -Parent $target
            New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
}

Write-Step "Preparing Python virtual environment"
$venvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
$venvPythonw = Join-Path $InstallDir ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $venvPython)) {
    try {
        & $PythonLauncher -3 -m venv (Join-Path $InstallDir ".venv")
    } catch {
        & python -m venv (Join-Path $InstallDir ".venv")
    }
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $InstallDir "requirements.txt")

Write-Step "Creating shortcuts"
$launcher = Join-Path $InstallDir "EffectPalette.pyw"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Effect Palette"
New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null
New-Shortcut `
    -Path (Join-Path $startMenuDir "Effect Palette.lnk") `
    -Target $venvPythonw `
    -Arguments "`"$launcher`"" `
    -WorkingDirectory $InstallDir `
    -Description "Launch Effect Palette"

if ($CreateDesktopShortcut) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    New-Shortcut `
        -Path (Join-Path $desktop "Effect Palette.lnk") `
        -Target $venvPythonw `
        -Arguments "`"$launcher`"" `
        -WorkingDirectory $InstallDir `
        -Description "Launch Effect Palette"
}

if ($CreateStartupShortcut) {
    $startup = [Environment]::GetFolderPath("Startup")
    New-Shortcut `
        -Path (Join-Path $startup "Effect Palette.lnk") `
        -Target $venvPythonw `
        -Arguments "`"$launcher`"" `
        -WorkingDirectory $InstallDir `
        -Description "Start Effect Palette with Windows"
}

Write-Step "Done"
Write-Host "$DisplayName installed at: $InstallDir" -ForegroundColor Green
Write-Host "Launch it from Start Menu or Desktop. Use -CreateStartupShortcut to start it with Windows." -ForegroundColor Green
Write-Host "Beta reports will be saved in Documents\EffectPalette_Beta_Report." -ForegroundColor Green
