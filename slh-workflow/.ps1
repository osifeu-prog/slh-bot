param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("check","diff","release","rollback")]
    [string]$Action,

    [string]$Message = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$BASELINE = "slh-baseline-2026-08-09"

function Assert-Clean {
    $status = git status --porcelain
    if ($status) {
        Write-Host "WORKTREE_NOT_CLEAN" -ForegroundColor Red
        git status --short
        throw "STOP: local changes exist"
    }
}

function Assert-Sync {
    git fetch origin | Out-Null

    $head = git rev-parse HEAD
    $remote = git rev-parse origin/main

    Write-Host "HEAD   = $head"
    Write-Host "ORIGIN = $remote"

    if ($head -ne $remote) {
        throw "STOP: HEAD and origin/main differ"
    }
}

if ($Action -eq "check") {

    Write-Host "`n=== SLH WORKFLOW CHECK ===" -ForegroundColor Cyan

    Assert-Sync

    Write-Host "`n=== COMPILE ===" -ForegroundColor Yellow
    python -m compileall -q .
    if ($LASTEXITCODE -ne 0) {
        throw "COMPILE_FAILED"
    }
    Write-Host "COMPILE_OK" -ForegroundColor Green

    Write-Host "`n=== WORKTREE ===" -ForegroundColor Yellow
    git status --short
    if (git status --porcelain) {
        throw "WORKTREE_NOT_CLEAN"
    }

    Write-Host "`n=== BASELINE TAG ===" -ForegroundColor Yellow
    git tag --points-at $BASELINE

    Write-Host "`n=== RESULT ===" -ForegroundColor Green
    Write-Host "SLH_WORKFLOW_CHECK_OK"
    exit 0
}

if ($Action -eq "diff") {

    Write-Host "`n=== SLH CHANGE REVIEW ===" -ForegroundColor Cyan

    git status --short

    Write-Host "`n=== FILES ===" -ForegroundColor Yellow
    git diff --name-status

    Write-Host "`n=== DIFF STAT ===" -ForegroundColor Yellow
    git diff --stat

    Write-Host "`n=== DIFF ===" -ForegroundColor Yellow
    git diff

    exit 0
}

if ($Action -eq "release") {

    if ([string]::IsNullOrWhiteSpace($Message)) {
        throw "Usage: .\slh-workflow.ps1 release -Message 'description'"
    }

    Write-Host "`n=== SLH RELEASE ===" -ForegroundColor Cyan

    git status --short

    Write-Host "`n=== COMPILE ===" -ForegroundColor Yellow
    python -m compileall -q .
    if ($LASTEXITCODE -ne 0) {
        throw "COMPILE_FAILED"
    }

    Write-Host "COMPILE_OK" -ForegroundColor Green

    Write-Host "`n=== DIFF ===" -ForegroundColor Yellow
    git diff --stat

    if (-not (git status --porcelain)) {
        throw "STOP: no changes to release"
    }

    Write-Host "`n=== COMMIT ===" -ForegroundColor Yellow
    git add -A
    git commit -m $Message

    Write-Host "`n=== PUSH ===" -ForegroundColor Yellow
    git push origin main

    Write-Host "`n=== VERIFY ===" -ForegroundColor Yellow
    git fetch origin | Out-Null

    $head = git rev-parse HEAD
    $remote = git rev-parse origin/main

    if ($head -ne $remote) {
        throw "PUSH_VERIFICATION_FAILED"
    }

    Write-Host "`n=== RELEASE COMPLETE ===" -ForegroundColor Green
    Write-Host "RELEASE=$head"
    Write-Host "SLH_RELEASE_OK"
    exit 0
}

if ($Action -eq "rollback") {

    Write-Host "`n=== SLH ROLLBACK ===" -ForegroundColor Red
    Write-Host "TARGET=$BASELINE"

    $answer = Read-Host "Type ROLLBACK to confirm"

    if ($answer -ne "ROLLBACK") {
        throw "ROLLBACK_CANCELLED"
    }

    git fetch origin | Out-Null
    git reset --hard $BASELINE
    git push --force-with-lease origin main

    Write-Host "`n=== ROLLBACK COMPLETE ===" -ForegroundColor Green
    git rev-parse HEAD
    exit 0
}
