[CmdletBinding()]
param(
    [string]$SkillName = "video-link-pipeline",
    [string]$SourceSkillsRoot = "skills",
    [string]$TargetSkillsRoot = "",
    [switch]$SkipValidate
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-DefaultTargetSkillsRoot {
    if ($env:CODEX_HOME) {
        return (Join-Path $env:CODEX_HOME "skills")
    }

    return (Join-Path $HOME ".codex\skills")
}

function Get-ValidatorPath {
    if ($env:CODEX_HOME) {
        return (Join-Path $env:CODEX_HOME "skills\.system\skill-creator\scripts\quick_validate.py")
    }

    return (Join-Path $HOME ".codex\skills\.system\skill-creator\scripts\quick_validate.py")
}

$repoRoot = (Get-Location).Path
$resolvedSourceRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot $SourceSkillsRoot)).Path
$sourceSkillPath = Join-Path $resolvedSourceRoot $SkillName

if (-not (Test-Path -LiteralPath $sourceSkillPath)) {
    throw "source skill not found: $sourceSkillPath"
}

if ([string]::IsNullOrWhiteSpace($TargetSkillsRoot)) {
    $TargetSkillsRoot = Get-DefaultTargetSkillsRoot
}

$resolvedTargetRoot = [System.IO.Path]::GetFullPath($TargetSkillsRoot)
$targetSkillPath = Join-Path $resolvedTargetRoot $SkillName
$validatorPath = Get-ValidatorPath

Write-Host "Syncing Codex skill" -ForegroundColor Green
Write-Host "Source :" -NoNewline
Write-Host " $sourceSkillPath" -ForegroundColor Yellow
Write-Host "Target :" -NoNewline
Write-Host " $targetSkillPath" -ForegroundColor Yellow

Write-Step "prepare target directory"
New-Item -ItemType Directory -Path $resolvedTargetRoot -Force | Out-Null

if (Test-Path -LiteralPath $targetSkillPath) {
    Remove-Item -LiteralPath $targetSkillPath -Recurse -Force
}

Write-Step "copy skill files"
Copy-Item -LiteralPath $sourceSkillPath -Destination $targetSkillPath -Recurse

if (-not $SkipValidate) {
    if (-not (Test-Path -LiteralPath $validatorPath)) {
        throw "validator not found: $validatorPath"
    }

    Write-Step "validate installed skill"
    & python $validatorPath $targetSkillPath
    if ($LASTEXITCODE -ne 0) {
        throw "skill validation failed"
    }
}

Write-Host ""
Write-Host "Skill sync completed." -ForegroundColor Green
