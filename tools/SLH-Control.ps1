param(
    [ValidateSet("dashboard","status","map","watch","journal","tasks","sync","pc","logs","deploycheck","varnames","use","pull","help")]
    [string]$Command = "dashboard",

    [string]$Target = "main",

    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptRoot "..")).Path
$ConfigPath = Join-Path $RepoRoot "config\slh_control_targets.json"

if (-not (Test-Path $ConfigPath)) {
    throw "SLH Control config not found: $ConfigPath"
}

$Config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Write-SlhTitle {
    param([string]$Text, [ConsoleColor]$Color = [ConsoleColor]::Yellow)
    Write-Host ""
    Write-Host "==== $Text ====" -ForegroundColor $Color
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Get-SlhTarget {
    param([string]$Name)
    $property = $Config.targets.PSObject.Properties[$Name]
    if ($null -eq $property) {
        throw "Unknown SLH target '$Name'. Use: main, web, api"
    }
    return $property.Value
}

function Invoke-SlhGit {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
    & git -C $RepoRoot @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git command failed with exit code $LASTEXITCODE"
    }
}

function Invoke-SlhRailway {
    param(
        [Parameter(Mandatory = $true)][psobject]$RailwayTarget,
        [Parameter(Mandatory = $true)][string[]]$RailwayArgs
    )
    & railway @RailwayArgs --project $RailwayTarget.railway_project_id --environment $RailwayTarget.environment --service $RailwayTarget.service
    if ($LASTEXITCODE -ne 0) {
        throw "railway command failed with exit code $LASTEXITCODE"
    }
}

function Get-LocalAgentProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*slh_agent.py*" }
}

function Show-SlhBanner {
    Write-Host ""
    Write-Host "==============================" -ForegroundColor Cyan
    Write-Host "        SLH OS CONTROL" -ForegroundColor Cyan
    Write-Host "==============================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Project: $($Config.repo.full_name)" -ForegroundColor Gray
    Write-Host "Repo branch: $($Config.repo.branch)" -ForegroundColor Gray
    Write-Host "Control mode: READ-ONLY by default" -ForegroundColor Green
}

function Show-GitSummary {
    Write-SlhTitle "GIT"
    $branch = (git -C $RepoRoot branch --show-current).Trim()
    $head = (git -C $RepoRoot rev-parse --short HEAD).Trim()
    $origin = (git -C $RepoRoot rev-parse --short origin/main 2>$null).Trim()
    $dirty = @(git -C $RepoRoot status --porcelain)

    Write-Host "Branch : $branch"
    Write-Host "HEAD   : $head"
    Write-Host "Origin : $(if ($origin) { $origin } else { 'unavailable' })"

    if ($dirty.Count -gt 0) {
        Write-Host "Tree   : DIRTY" -ForegroundColor Yellow
        $dirty | Select-Object -First 12 | ForEach-Object { Write-Host "  $_" }
        if ($dirty.Count -gt 12) {
            Write-Host "  ... more changes omitted"
        }
    } else {
        Write-Host "Tree   : CLEAN" -ForegroundColor Green
    }
}

function Show-LocalStateSummary {
    Write-SlhTitle "LOCAL STATE"
    $dbPath = Join-Path $RepoRoot "state\db.json"

    if (-not (Test-Path $dbPath)) {
        Write-Host "state/db.json not present locally. Railway Volume remains runtime-authoritative." -ForegroundColor DarkYellow
        return
    }

    $db = $dbPath.Replace("\","\\")
    $py = "import json; from pathlib import Path; d=json.loads(Path(r'$db').read_text(encoding='utf-8')); print('Users:',len(d.get('users',{}))); print('Agents:',len(d.get('agents',{}))); print('Tasks:',len(d.get('tasks',{}))); print('Ledger rows:',len(d.get('ledger',[]))); print('Revenue rows:',len(d.get('revenue_ledger',[])))"
    & python -c $py
}

function Show-PcSummary {
    Write-SlhTitle "PC AGENT"
    $agentPath = Join-Path $env:USERPROFILE "slh_agent.py"
    $batPath = Join-Path $env:USERPROFILE "slh_agent.bat"
    $secretPath = Join-Path $env:USERPROFILE "slh_mqtt_heartbeat_secret.txt"

    Write-Host "Agent : $agentPath"
    Write-Host "Start : $batPath"

    if (Test-Path $agentPath) {
        Write-Host "Agent file: PRESENT" -ForegroundColor Green
        $heartbeat = Select-String -Path $agentPath -Pattern "HEARTBEAT_TOPIC|publish_heartbeat|heartbeat_loop|PC_Osif2" -Quiet
        Write-Host "Heartbeat code: $(if ($heartbeat) { 'PRESENT' } else { 'MISSING' })"
    } else {
        Write-Host "Agent file: MISSING" -ForegroundColor Red
    }

    if (Test-Path $secretPath) {
        $secretLength = (Get-Content $secretPath -Raw -Encoding ASCII).Trim().Length
        Write-Host "Heartbeat secret: present (length $secretLength)" -ForegroundColor Green
    } else {
        Write-Host "Heartbeat secret: MISSING" -ForegroundColor Red
    }

    $procs = @(Get-LocalAgentProcesses)
    if ($procs.Count -gt 0) {
        Write-Host "Process : RUNNING ($($procs.Count))" -ForegroundColor Green
        $procs | ForEach-Object { Write-Host "  PID $($_.ProcessId)" }
    } else {
        Write-Host "Process : NOT RUNNING" -ForegroundColor Yellow
    }
}

function Show-RailwayTarget {
    param([string]$Name)
    $t = Get-SlhTarget $Name

    Write-SlhTitle "$($t.label) — Railway"
    Write-Host "Project : $($t.railway_project)"
    Write-Host "Service : $($t.service)"
    Write-Host "Env     : $($t.environment)"
    Write-Host "Role    : $($t.role)"

    try {
        Invoke-SlhRailway -RailwayTarget $t -RailwayArgs @("status")
    } catch {
        Write-Host "Railway status unavailable: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Show-Dashboard {
    Show-SlhBanner
    Show-GitSummary
    Show-PcSummary

    Write-SlhTitle "TARGETS"
    foreach ($name in @("main","web","api")) {
        $t = Get-SlhTarget $name
        Write-Host ("{0,-6} {1,-12} {2}" -f $name.ToUpper(), $t.label, $t.railway_project)
    }

    Show-LocalStateSummary
    Show-RailwayTarget -Name $Target

    Write-SlhTitle "NEXT"
    Write-Host "slhstatus        -> Git + selected Railway target"
    Write-Host "slhwatch         -> health audit"
    Write-Host "slhpc             -> PC agent + heartbeat"
    Write-Host "slhmap           -> architecture / source-of-truth map"
    Write-Host "slhuse web       -> switch Railway target to WEB"
    Write-Host "slhuse api       -> switch Railway target to API"
    Write-Host "slhlogs          -> recent logs for selected target"
}

function Show-Status {
    Show-SlhBanner
    Show-GitSummary
    Show-RailwayTarget -Name $Target
    Show-PcSummary
}

function Show-Map {
    Show-SlhBanner
    Write-SlhTitle "SOURCE OF TRUTH"
    Write-Host "GitHub : versioned code, review, CI, release history"
    Write-Host "Railway: live deployment/runtime/infrastructure state"
    Write-Host "Bot state: state/db.json on the Railway Volume"
    Write-Host "API/Postgres: separate API/data plane"
    Write-Host "PC: local operator/agent node"

    Write-SlhTitle "FLOW"
    Write-Host "PowerShell Control Tower"
    Write-Host "        -> Git / PR / CI"
    Write-Host "        -> Railway targets"
    Write-Host "        -> Telegram / Mini App / API"
    Write-Host "        -> PC_Osif2 heartbeat / agent"
    Write-Host ""
    Write-Host "No financial/token mutation is performed by this tool."
}

function Show-Watch {
    Show-SlhBanner
    Write-SlhTitle "HEALTH WATCH"

    Require-Command git
    Require-Command python
    Require-Command railway

    Write-Host "git diff --check"
    & git -C $RepoRoot diff --check
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PASS" -ForegroundColor Green
    } else {
        Write-Host "FAIL" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "Python syntax"
    & python -m compileall -q (Join-Path $RepoRoot "core") (Join-Path $RepoRoot "handlers")
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PASS" -ForegroundColor Green
    } else {
        Write-Host "FAIL" -ForegroundColor Red
    }

    Show-PcSummary
    Show-RailwayTarget -Name $Target
}

function Show-Journal {
    Write-SlhTitle "SLH JOURNAL"
    $dbPath = Join-Path $RepoRoot "state\db.json"

    if (-not (Test-Path $dbPath)) {
        Write-Host "Local state is not mounted here; use /journal in the runtime for canonical journal state." -ForegroundColor Yellow
        return
    }

    $db = $dbPath.Replace("\","\\")
    $py = "import json; from pathlib import Path; d=json.loads(Path(r'$db').read_text(encoding='utf-8')); rows=d.get('journal',[]); rows=list(rows.values()) if isinstance(rows,dict) else rows; [print(r) for r in rows[-10:]]; print('Journal rows:',len(rows))"
    & python -c $py
}

function Show-Tasks {
    Write-SlhTitle "SLH TASKS"
    $dbPath = Join-Path $RepoRoot "state\db.json"

    if (-not (Test-Path $dbPath)) {
        Write-Host "Local state is not mounted here; use /tasks in the runtime for canonical tasks." -ForegroundColor Yellow
        return
    }

    $db = $dbPath.Replace("\","\\")
    $py = "import json; from pathlib import Path; d=json.loads(Path(r'$db').read_text(encoding='utf-8')); tasks=d.get('tasks',{}); items=list(tasks.items()) if isinstance(tasks,dict) else list(enumerate(tasks if isinstance(tasks,list) else [])); [print(k,v) for k,v in items[-15:]]; print('Task rows:',len(items))"
    & python -c $py
}

function Sync-Check {
    Require-Command git
    Require-Command railway

    Write-SlhTitle "SYNC"
    Invoke-SlhGit fetch origin
    Show-GitSummary
    Show-RailwayTarget -Name $Target
    Write-Host ""
    Write-Host "No automatic pull, push, merge, deploy, financial mutation, or token mutation is performed."
}

function Show-Logs {
    Require-Command railway
    $t = Get-SlhTarget $Target
    Write-SlhTitle "$($t.label) LOGS"
    Invoke-SlhRailway -RailwayTarget $t -RailwayArgs @("logs")
}

function Show-DeployCheck {
    Require-Command railway
    $t = Get-SlhTarget $Target
    Write-SlhTitle "$($t.label) DEPLOY CHECK"
    Invoke-SlhRailway -RailwayTarget $t -RailwayArgs @("status")
}

function Show-VariableNames {
    Require-Command railway
    $t = Get-SlhTarget $Target
    Write-SlhTitle "$($t.label) VARIABLE NAMES"
    Write-Host "Only names are shown; secret values are never printed."

    $raw = & railway variable list --service $t.service --environment $t.environment --json
    if ($LASTEXITCODE -ne 0) {
        throw "railway variable list failed"
    }

    try {
        $obj = $raw | ConvertFrom-Json
        if ($obj.variables) {
            $obj.variables.PSObject.Properties.Name | Sort-Object | ForEach-Object { Write-Host $_ }
        }
    } catch {
        Write-Host "Could not safely parse variable names." -ForegroundColor Yellow
    }
}

function Use-Target {
    param([string]$Name)
    Require-Command railway
    $t = Get-SlhTarget $Name

    Write-SlhTitle "LINK"
    & railway link --project $t.railway_project_id --environment $t.environment_id --service $t.service_id
    if ($LASTEXITCODE -ne 0) {
        throw "Railway link failed"
    }
    Write-Host "Linked to $($t.railway_project) / $($t.service)." -ForegroundColor Green
}

function Pull-Main {
    if (-not $Force) {
        Write-Host "Blocked by default. Run: slhpull -Force" -ForegroundColor Yellow
        return
    }

    $dirty = @(git -C $RepoRoot status --porcelain)
    if ($dirty.Count -gt 0) {
        throw "Working tree is dirty. Commit or stash local changes before pulling main."
    }

    Invoke-SlhGit fetch origin
    Invoke-SlhGit pull --ff-only origin main
    Write-Host "Fast-forwarded local main." -ForegroundColor Green
}

function Show-Help {
    Show-SlhBanner
    Write-Host ""
    Write-Host "Core commands"
    Write-Host "  slh                 Dashboard"
    Write-Host "  slhstatus           Git + Railway + PC"
    Write-Host "  slhmap              Source-of-truth / architecture"
    Write-Host "  slhwatch            Health audit"
    Write-Host "  slhjournal          Read journal state"
    Write-Host "  slhtasks            Read task state"
    Write-Host "  slhsync             Fetch/compare/verify"
    Write-Host "  slhpc               PC agent / heartbeat"
    Write-Host "  slhlogs             Railway logs"
    Write-Host "  slhdeploycheck      Railway deployment status"
    Write-Host "  slhvarnames         Variable names only"
    Write-Host "  slhuse main|web|api Switch Railway target"
    Write-Host "  slhpull -Force      Fast-forward local main"
    Write-Host ""
    Write-Host "Safety: read-only by default; no railway up; no secret values; no financial/token mutations."
}

switch ($Command) {
    "dashboard"   { Show-Dashboard }
    "status"      { Show-Status }
    "map"         { Show-Map }
    "watch"       { Show-Watch }
    "journal"     { Show-Journal }
    "tasks"       { Show-Tasks }
    "sync"        { Sync-Check }
    "pc"          { Show-PcSummary }
    "logs"        { Show-Logs }
    "deploycheck" { Show-DeployCheck }
    "varnames"    { Show-VariableNames }
    "use"         { Use-Target -Name $Target }
    "pull"        { Pull-Main }
    "help"        { Show-Help }
    default       { Show-Help }
}
