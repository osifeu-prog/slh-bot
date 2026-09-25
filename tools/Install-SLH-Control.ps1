# Install/update SLH OS Control Tower commands in the current user's PowerShell profile.
# Safe to rerun: the managed block is replaced, not duplicated.

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ControlScript = Join-Path $RepoRoot "tools\SLH-Control.ps1"

if (-not (Test-Path $ControlScript)) {
    throw "Control script not found: $ControlScript"
}

$profilePath = $PROFILE
$profileDir = Split-Path -Parent $profilePath

if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
}

if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
}

$current = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
if ($null -eq $current) {
    $current = ""
}

$start = "# >>> SLH OS CONTROL TOWER >>>"
$end = "# <<< SLH OS CONTROL TOWER <<<"

$block = @'
__START__
function slh        { & "__CONTROL_SCRIPT__" -Command dashboard @args }
function slhstatus  { & "__CONTROL_SCRIPT__" -Command status @args }
function slhmap     { & "__CONTROL_SCRIPT__" -Command map @args }
function slhwatch   { & "__CONTROL_SCRIPT__" -Command watch @args }
function slhjournal { & "__CONTROL_SCRIPT__" -Command journal @args }
function slhtasks   { & "__CONTROL_SCRIPT__" -Command tasks @args }
function slhsync    { & "__CONTROL_SCRIPT__" -Command sync @args }
function slhpc      { & "__CONTROL_SCRIPT__" -Command pc @args }
function slhlogs    { & "__CONTROL_SCRIPT__" -Command logs @args }
function slhdeploycheck { & "__CONTROL_SCRIPT__" -Command deploycheck @args }
function slhvarnames { & "__CONTROL_SCRIPT__" -Command varnames @args }
function slhuse { param([string]$name="main") & "__CONTROL_SCRIPT__" -Command use -Target $name @args }
function slhpull    { & "__CONTROL_SCRIPT__" -Command pull @args }
function slhhelp    { & "__CONTROL_SCRIPT__" -Command help @args }
__END__
'@

$block = $block.Replace("__START__", $start).Replace("__END__", $end).Replace("__CONTROL_SCRIPT__", $ControlScript)

$pattern = "(?s)" + [regex]::Escape($start) + ".*?" + [regex]::Escape($end)

if ($current -match $pattern) {
    $updated = [regex]::Replace($current, $pattern, $block)
} else {
    $updated = $current + [Environment]::NewLine + $block + [Environment]::NewLine
}

Set-Content -Path $profilePath -Value $updated -Encoding UTF8

Write-Host "SLH CONTROL TOWER INSTALLED" -ForegroundColor Green
Write-Host "Profile: $profilePath"
Write-Host "Reload PowerShell with: . " -NoNewline
Write-Host '$PROFILE'
