param(
    [switch]$Json
)

$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$ControlRoot = Join-Path $Root "_slh_map\control"

$StatePath = Join-Path $ControlRoot "CONTROL_STATE.json"

if (-not (Test-Path $StatePath)) {
    Write-Host "CONTROL STATE NOT FOUND." -ForegroundColor Red
    Write-Host "Run the master control audit first."
    exit 2
}

$State = Get-Content $StatePath -Raw | ConvertFrom-Json

if ($Json) {
    $State | ConvertTo-Json -Depth 30
    exit 0
}

Clear-Host

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "                    SLH OS CONTROL" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "PROJECT        : $($State.project)"
Write-Host "BRANCH         : $($State.git.branch)"
Write-Host "HEAD           : $($State.git.head)"
Write-Host "WORKTREE       : $($State.git.working_tree_changes) changes"
Write-Host ""

Write-Host "STRUCTURE" -ForegroundColor Yellow
Write-Host "  nested _slh_map       : $($State.structural_safety.nested_slh_map_count)"
Write-Host "  nested backups        : $($State.structural_safety.nested_encoding_backups_count)"
Write-Host "  backup root exists    : $($State.structural_safety.encoding_backups_exists)"
Write-Host ""

Write-Host "COMMAND SURFACE" -ForegroundColor Yellow
Write-Host "  available             : $($State.command_surface.available)/$($State.command_surface.expected)"
Write-Host "  missing               : $($State.command_surface.missing)"
Write-Host ""

Write-Host "DEPLOYMENT" -ForegroundColor Yellow
Write-Host "  Railway CLI           : $($State.deployment.railway_cli_available)"
Write-Host "  Railway checked       : $($State.deployment.railway_status_checked)"
Write-Host "  deployment verified  : $($State.deployment.deployment_verified)"
Write-Host ""

Write-Host "LAUNCH" -ForegroundColor Yellow
Write-Host "  state                 : $($State.launch.state)"
Write-Host "  readiness             : $($State.launch.readiness_percent)%"
Write-Host "  target                : $($State.launch.target)"
Write-Host ""

Write-Host "PATH VERIFICATION" -ForegroundColor Yellow
Write-Host "  investor path         : $($State.investor_path.verified)"
Write-Host "  user path             : $($State.user_path.verified)"
Write-Host "  security              : $($State.security.verified)"
Write-Host ""

if ($State.blockers.Count -gt 0) {

    Write-Host "BLOCKERS" -ForegroundColor Red

    foreach ($Blocker in $State.blockers) {
        Write-Host "  [!] $Blocker" -ForegroundColor Red
    }

} else {

    Write-Host "BLOCKERS: NONE" -ForegroundColor Green
}

Write-Host ""
Write-Host "CONTROL FILES" -ForegroundColor DarkCyan
Write-Host "  $ControlRoot"
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
