param(
    [string]$Version = "0.1.0-beta",
    [string]$Python = "python",
    [switch]$InstallBuildDeps,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ReleaseDir = Join-Path $Root "release"
$StageRoot = Join-Path $env:TEMP "EffectPalette_Installer_Staging"
$StageDir = Join-Path $StageRoot "EffectPalette"
$PyInstallerSpec = Join-Path $Root "packaging\pyinstaller\EffectPalette.spec"
$InnoScript = Join-Path $Root "packaging\inno\EffectPalette.iss"
$PyInstallerWorkRoot = Join-Path $env:TEMP "EffectPalette_PyInstaller_Build"
$PyInstallerDistRoot = Join-Path $env:TEMP "EffectPalette_PyInstaller_Dist"
$PyInstallerDist = Join-Path $PyInstallerDistRoot "EffectPalette"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked($File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $File $($Arguments -join ' ')"
    }
}

function Copy-FileToStage($RelativePath) {
    $source = Join-Path $Root $RelativePath
    $target = Join-Path $StageDir $RelativePath
    $parent = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force
}

function Copy-DirToStage($RelativePath) {
    $source = Join-Path $Root $RelativePath
    $target = Join-Path $StageDir $RelativePath
    if (Test-Path $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
    Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
}

function Get-InnoCompiler() {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 5\ISCC.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    $fromPath = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    return $null
}

Write-Step "Checking Python build dependencies"
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Python -c "import PyInstaller" 2>$null
$pyinstallerExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference

if ($pyinstallerExitCode -ne 0) {
    if (-not $InstallBuildDeps) {
        throw "PyInstaller is not installed. Run: .\packaging\build_release.ps1 -InstallBuildDeps"
    }

    Invoke-Checked $Python @("-m", "pip", "--isolated", "install", "--upgrade", "pip")
    Invoke-Checked $Python @("-m", "pip", "--isolated", "install", "-r", (Join-Path $Root "requirements.txt"))
    Invoke-Checked $Python @("-m", "pip", "--isolated", "install", "pyinstaller")
}

Write-Step "Building FX.palette.exe with PyInstaller"
if (Test-Path $PyInstallerWorkRoot) {
    Remove-Item -LiteralPath $PyInstallerWorkRoot -Recurse -Force
}
if (Test-Path $PyInstallerDistRoot) {
    Remove-Item -LiteralPath $PyInstallerDistRoot -Recurse -Force
}

Invoke-Checked $Python @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--workpath", $PyInstallerWorkRoot,
    "--distpath", $PyInstallerDistRoot,
    $PyInstallerSpec
)

if (-not (Test-Path (Join-Path $PyInstallerDist "FX.palette.exe"))) {
    throw "PyInstaller output not found: $PyInstallerDist"
}

Write-Step "Preparing clean installer staging folder"
if (Test-Path $StageRoot) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
if (Test-Path $StageDir) {
    Remove-Item -LiteralPath $StageDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
Copy-Item -Path (Join-Path $PyInstallerDist "*") -Destination $StageDir -Recurse -Force

Write-Step "Copying CEP extension files"
Copy-FileToStage "app.py"
Copy-FileToStage "bridge.js"
Copy-FileToStage "index.html"
Copy-FileToStage "worker.html"
Copy-FileToStage "README.md"
Copy-FileToStage "RELATORIO_EFFECT_PALETTE.md"
Copy-DirToStage "CSXS"
Copy-DirToStage "lib"
Copy-DirToStage "scripts"

Write-Step "Copying clean data templates"
New-Item -ItemType Directory -Force -Path (Join-Path $StageDir "data") | Out-Null
Copy-FileToStage "data\generic_item_templates.json"
Copy-FileToStage "data\generic_item_templates.example.json"

Write-Step "Copying template project"
New-Item -ItemType Directory -Force -Path (Join-Path $StageDir "template_project") | Out-Null
Copy-FileToStage "template_project\template_project.prproj"
$audioPreviews = Join-Path $Root "template_project\Adobe Premiere Pro Audio Previews"
if (Test-Path $audioPreviews) {
    Copy-Item -LiteralPath $audioPreviews -Destination (Join-Path $StageDir "template_project\Adobe Premiere Pro Audio Previews") -Recurse -Force
}

if ($SkipInstaller) {
    Write-Step "Skipping Inno Setup installer"
    Write-Host "Staged app: $StageDir" -ForegroundColor Green
    exit 0
}

Write-Step "Building setup executable with Inno Setup"
$innoCompiler = Get-InnoCompiler
if (-not $innoCompiler) {
    throw "Inno Setup compiler not found. Install Inno Setup 6 or run with -SkipInstaller to only create the staged app."
}

Invoke-Checked $innoCompiler @("/DMyAppVersion=$Version", "/DSourceDir=$StageDir", $InnoScript)

Write-Step "Release ready"
Write-Host "Installer output folder: $ReleaseDir" -ForegroundColor Green
