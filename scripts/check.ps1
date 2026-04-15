[CmdletBinding()]
param(
    [switch]$SkipPipCheck,
    [switch]$SkipCompileAll,
    [switch]$SkipRuff,
    [switch]$SkipPytest,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string[]]$Command
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    Write-Host ($Command -join " ") -ForegroundColor DarkGray
    & $Command[0] $Command[1..($Command.Length - 1)]
    if ($LASTEXITCODE -ne 0) {
        throw "step failed: $Name"
    }
}

Write-Host "Running local validation checks for video-link-pipeline" -ForegroundColor Green
Write-Host "Python executable:" -NoNewline
Write-Host " $(& python -c "import sys; print(sys.executable)")" -ForegroundColor Yellow

if (-not $SkipPipCheck) {
    Invoke-Step -Name "pip check" -Command @("python", "-m", "pip", "check")
}

if (-not $SkipCompileAll) {
    Invoke-Step -Name "compileall" -Command @("python", "-m", "compileall", "src", "tests")
}

if (-not $SkipRuff) {
    Invoke-Step -Name "ruff" -Command @("python", "-m", "ruff", "check", ".")
}

if (-not $SkipPytest) {
    Invoke-Step -Name "pytest" -Command @("python", "-m", "pytest")
}

if (-not $SkipBuild) {
    Invoke-Step -Name "build" -Command @("python", "-m", "build")
}

Write-Host ""
Write-Host "All requested checks completed." -ForegroundColor Green
