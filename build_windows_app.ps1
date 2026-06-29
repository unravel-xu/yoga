$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if ($env:PYTHON_BIN) {
    $pythonCommand = $env:PYTHON_BIN
    $pythonPrefixArgs = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = "py"
    $pythonPrefixArgs = @("-3.11")
} else {
    $pythonCommand = "python"
    $pythonPrefixArgs = @()
}

function Invoke-Python {
    param(
        [string[]]$PythonArguments
    )

    & $pythonCommand @pythonPrefixArgs @PythonArguments

    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

Write-Host "Using Python:"
Invoke-Python -PythonArguments @("--version")

Invoke-Python -PythonArguments @(
    "-m", "pip", "install", "--upgrade", "pip"
)
Invoke-Python -PythonArguments @(
    "-m", "pip", "install",
    "-r", "requirements.txt",
    "-r", "requirements-build.txt"
)
Invoke-Python -PythonArguments @(
    "-m", "PyInstaller",
    "--clean", "--noconfirm",
    "YogaPoseCoachWindows.spec"
)

$zipPath = Join-Path $PSScriptRoot "dist\YogaPoseCoach-Windows.zip"
$appDirectory = Join-Path $PSScriptRoot "dist\YogaPoseCoach"

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Compress-Archive `
    -Path (Join-Path $appDirectory "*") `
    -DestinationPath $zipPath `
    -CompressionLevel Optimal

Write-Host ""
Write-Host "Built Windows app:"
Write-Host "  dist\YogaPoseCoach\YogaPoseCoach.exe"
Write-Host ""
Write-Host "Share this ZIP:"
Write-Host "  dist\YogaPoseCoach-Windows.zip"
