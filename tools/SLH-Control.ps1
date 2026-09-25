param(
    [ValidateSet("dashboard","status","map","watch","journal","tasks","sync","pc","logs","deploycheck","varnames","use","pull","redeploy","doctor","help")]
    [string]$Command = "dashboard",
    [string]$Target = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptRoot "..")).Path
$ConfigPath = Join-Path $RepoRoot "config\slh_control_targets.json"
$LocalControlDir = Join-Path $env:USERPROFILE ".slh-control"
$ActiveTargetPath = Join-Path $LocalControlDir "active-target"

if (-not (Test-Path $ConfigPath)) { throw "SLH Control config not found: $ConfigPath" }
$Config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Write-SlhTitle {
    param([string]$Text, [ConsoleColor]$Color = [ConsoleColor]::Yellow)
    Write-Host ""
    Write-Host "==== $Text ====" -ForegroundColor $Color
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { throw "Required command not found: $Name" }
}

function Get-ActiveTargetName {
    if (Test-Path $ActiveTargetPath) {
        $name = (Get-Content $ActiveTargetPath -Raw -Encoding UTF8).Trim().ToLower()
        if ($Config.targets.PSObject.Properties.Name -contains $name) { return $name }
    }
    return "main"
}

function Get-SlhTarget {
    param([string]$Name)
    if ([string]::IsNullOrWhiteSpace($Name)) { $Name = Get-ActiveTargetName }
    $property = $Config.targets.PSObject.Properties[$Name.ToLower()]
    if ($null -eq $property) { throw "Unknown SLH target '$Name'. Valid: main, web, api" }
    return $property.Value
}

function Ensure-SlhTarget {
    param([string]$Name)
    if ((Get-ActiveTargetName) -eq $Name.ToLower()) { return }

    Require-Command railway
    $t = Get-SlhTarget $Name
    if (-not (Test-Path $LocalControlDir)) { New-Item -ItemType Directory -Path $LocalControlDir -Force | Out-Null }

    & railway link --workspace $Config.workspace_id --project $t.railway_project_id --environment $t.environment_id --service $t.service_id
    if ($LASTEXITCODE -ne 0) { throw "Railway link failed" }

    Set-Content -Path $ActiveTargetPath -Value $Name.ToLower() -Encoding ASCII
}

function Get-LocalAgentProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*slh_agent.py*" }
}

function Show-SlhBanner {
    Write-Host ""
    Write-Host "==============================" -ForegroundColor Cyan
    Write-Host "        SLH OS CONTROL" -ForegroundColor Cyan
    Write-Host "        CONTROL TOWER v2" -ForegroundColor Yellow
    Write-Host "==============================" -ForegroundColor Cyan
    Write-Host "Repo  : $($Config.repo.full_name)" -ForegroundColor Gray
    Write-Host "Target: $(Get-ActiveTargetName)" -ForegroundColor Green
    Write-Host "Mode  : READ-ONLY by default" -ForegroundColor Green
}

function Show-GitSummary {
    Write-SlhTitle "GIT"
    Require-Command git
    $branch = (git -C $RepoRoot branch --show-current).Trim()
    $head = (git -C $RepoRoot rev-parse --short HEAD).Trim()
    $origin = (git -C $RepoRoot rev-parse --short origin/main 2>$null).Trim()
    $dirty = @(git -C $RepoRoot status --porcelain)
    Write-Host "Branch : $branch"
    Write-Host "HEAD   : $head"
    Write-Host "Origin : $(if ($origin) { $origin } else { 'unavailable' })"
    if ($dirty.Count -eq 0) {
        Write-Host "Tree   : CLEAN" -ForegroundColor Green
    } else {
        Write-Host "Tree   : DIRTY ($($dirty.Count) changes)" -ForegroundColor Yellow
        $dirty | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }
    }
}

function Show-PcSummary {
    Write-SlhTitle "PC / AGENT"
    $agentPath = Join-Path $env:USERPROFILE "slh_agent.py"
    $launcherPath = Join-Path $env:USERPROFILE "slh_agent.bat"
    $secretPath = Join-Path $env:USERPROFILE "slh_mqtt_heartbeat_secret.txt"

    Write-Host "Agent : $agentPath"
    Write-Host "Start : $launcherPath"

    if (Test-Path $agentPath) {
        $heartbeat = Select-String -Path $agentPath -Pattern "HEARTBEAT_TOPIC|publish_heartbeat|heartbeat_loop|PC_Osif2" -Quiet
        if ($heartbeat) { Write-Host "Heartbeat code: PRESENT" -ForegroundColor Green }
        else { Write-Host "Heartbeat code: MISSING" -ForegroundColor Red }
    } else { Write-Host "Agent file: MISSING" -ForegroundColor Red }

    if (Test-Path $secretPath) {
        $len = (Get-Content $secretPath -Raw -Encoding ASCII).Trim().Length
        Write-Host "Heartbeat secret: PRESENT (length $len)" -ForegroundColor Green
    } else { Write-Host "Heartbeat secret: MISSING" -ForegroundColor Red }

    $procs = @(Get-LocalAgentProcesses)
    if ($procs.Count -gt 0) {
        Write-Host "Process : RUNNING ($($procs.Count))" -ForegroundColor Green
        $procs | ForEach-Object { Write-Host "  PID $($_.ProcessId)" }
    } else { Write-Host "Process : NOT RUNNING" -ForegroundColor Yellow }
}

function Show-Railway {
    param([string]$Name)
    Require-Command railway
    Ensure-SlhTarget $Name
    $t = Get-SlhTarget $Name
    Write-SlhTitle "$($t.label) / Railway"
    Write-Host "Project : $($t.railway_project)"
    Write-Host "Service : $($t.service)"
    Write-Host "Env     : $($t.environment)"
    Write-Host "Role    : $($t.role)"
    & railway status
    if ($LASTEXITCODE -ne 0) { Write-Host "Railway status returned exit code $LASTEXITCODE" -ForegroundColor Yellow }
}

function Get-RailwayStatusObject {
    param([object]$Target)
    $raw = & railway status --json --service $Target.service --environment $Target.environment
    if ($LASTEXITCODE -ne 0) { throw "railway status --json failed" }
    try { return ($raw | ConvertFrom-Json) } catch { throw "Could not parse railway status JSON" }
}

function Show-TargetIntegrity {
    param([string]$Name)
    Require-Command railway
    $t = Get-SlhTarget $Name
    $active = Get-ActiveTargetName
    Write-SlhTitle "TARGET INTEGRITY"

    $ok = $true
    Write-Host ("CONFIG TARGET       {0} / {1}" -f $Name.ToLower(),$t.railway_project)
    Write-Host ("ACTIVE TARGET       {0}" -f $active)

    if ($active -ne $Name.ToLower()) {
        $ok = $false
        Write-Host "ACTIVE TARGET       MISMATCH" -ForegroundColor Yellow
    } else {
        Write-Host "ACTIVE TARGET       MATCH" -ForegroundColor Green
    }

    try {
        $obj = Get-RailwayStatusObject $t
        $projectId = if ($obj.project.id) { [string]$obj.project.id } elseif ($obj.projectId) { [string]$obj.projectId } else { "" }
        $projectName = if ($obj.project.name) { [string]$obj.project.name } elseif ($obj.name) { [string]$obj.name } else { "" }
        $envId = if ($obj.environment.id) { [string]$obj.environment.id } elseif ($obj.environmentId) { [string]$obj.environmentId } else { "" }
        $envName = if ($obj.environment.name) { [string]$obj.environment.name } elseif ($obj.environmentName) { [string]$obj.environmentName } else { "" }

        $serviceObj = $null
        if ($obj.service) { $serviceObj = $obj.service }
        elseif ($obj.linkedService) { $serviceObj = $obj.linkedService }
        elseif ($obj.services) { $serviceObj = @($obj.services | Where-Object { $_.name -eq $t.service -or $_.id -eq $t.service_id } | Select-Object -First 1) }
        $serviceId = if ($serviceObj.id) { [string]$serviceObj.id } else { "" }
        $serviceName = if ($serviceObj.name) { [string]$serviceObj.name } else { "" }

        $projectMatch = ($projectId -eq [string]$t.railway_project_id -and $projectName -eq [string]$t.railway_project)
        $envMatch = ($envId -eq [string]$t.environment_id -and $envName -eq [string]$t.environment)
        $serviceMatch = ($serviceId -eq [string]$t.service_id -and $serviceName -eq [string]$t.service)

        Write-Host ("RAILWAY PROJECT     {0}" -f $(if ($projectMatch) { "MATCH" } else { "MISMATCH" })) -ForegroundColor $(if ($projectMatch) { "Green" } else { "Red" })
        Write-Host ("RAILWAY ENV         {0}" -f $(if ($envMatch) { "MATCH" } else { "MISMATCH" })) -ForegroundColor $(if ($envMatch) { "Green" } else { "Red" })
        Write-Host ("RAILWAY SERVICE     {0}" -f $(if ($serviceMatch) { "MATCH" } else { "MISMATCH" })) -ForegroundColor $(if ($serviceMatch) { "Green" } else { "Red" })

        if (-not ($projectMatch -and $envMatch -and $serviceMatch)) { $ok = $false }
    } catch {
        $ok = $false
        Write-Host "RAILWAY TARGET      CHECK FAILED: $($_.Exception.Message)" -ForegroundColor Red
    }

    if ($ok) {
        Write-Host "TARGET INTEGRITY    PASS" -ForegroundColor Green
    } else {
        Write-Host "TARGET INTEGRITY    CHECK REQUIRED" -ForegroundColor Yellow
        Write-Host "Run: slhuse $Name" -ForegroundColor Yellow
    }
}

function Get-RailwayLogMessages {
    param([object]$Target)
    $raw = & railway logs --latest --lines 120 --json --filter "PC_Osif2" --service $Target.service --environment $Target.environment
    if ($LASTEXITCODE -ne 0) { throw "railway logs --json failed" }
    try { return ($raw | ConvertFrom-Json) } catch { throw "Could not parse railway logs JSON" }
}

function Get-HeartbeatEntries {
    param([object]$Object)
    $items = @()
    function Walk-HeartbeatObject {
        param([object]$Node)
        if ($null -eq $Node) { return }
        if ($Node -is [System.Collections.IEnumerable] -and $Node -isnot [string]) {
            foreach ($item in $Node) { Walk-HeartbeatObject $item }
            return
        }
        if ($Node.PSObject.Properties.Name -contains "message") {
            $message = [string]$Node.message
            if ($message -match "PC_Osif2") {
                $stamp = ""
                if ($Node.PSObject.Properties.Name -contains "timestamp") { $stamp = [string]$Node.timestamp }
                $items += [pscustomobject]@{ Timestamp = $stamp; Message = $message }
            }
        }
        foreach ($p in $Node.PSObject.Properties) {
            if ($p.Name -notin @("message","timestamp")) { Walk-HeartbeatObject $p.Value }
        }
    }
    Walk-HeartbeatObject $Object
    return $items
}

function Show-HeartbeatStatus {
    param([string]$Name)
    Require-Command railway
    $t = Get-SlhTarget $Name
    Write-SlhTitle "PC HEARTBEAT"
    try {
        $obj = Get-RailwayLogMessages $t
        $entries = @(Get-HeartbeatEntries $obj)
        $online = @($entries | Where-Object { $_.Message -match "ONLINE PC_Osif2" })
        $reject = @($entries | Where-Object { $_.Message -match "REJECTED PC_Osif2" })
        $lastOnline = $online | Select-Object -Last 1
        $lastReject = $reject | Select-Object -Last 1

        if ($lastOnline) { Write-Host "PC_Osif2           ONLINE" -ForegroundColor Green }
        elseif ($lastReject) { Write-Host "PC_Osif2           AUTH REJECTED" -ForegroundColor Red }
        else { Write-Host "PC_Osif2           NO RECENT SIGNAL" -ForegroundColor Yellow }

        if ($lastOnline) { Write-Host "Last ONLINE        $($lastOnline.Timestamp)" }
        if ($lastReject) { Write-Host "Last REJECT        $($lastReject.Timestamp)" }

        if ($lastOnline -and $lastReject) {
            try {
                if ([datetimeoffset]::Parse($lastOnline.Timestamp) -gt [datetimeoffset]::Parse($lastReject.Timestamp)) {
                    Write-Host "Heartbeat auth     PASS" -ForegroundColor Green
                } else {
                    Write-Host "Heartbeat auth     CHECK REQUIRED" -ForegroundColor Yellow
                }
            } catch {
                Write-Host "Heartbeat auth     ONLINE SIGNAL FOUND" -ForegroundColor Green
            }
        }
    } catch {
        Write-Host "Heartbeat check    FAILED: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Show-Dashboard {
    Show-SlhBanner
    Show-GitSummary
    Show-PcSummary
    Write-SlhTitle "RAILWAY TARGETS"
    $active = Get-ActiveTargetName
    foreach ($name in @("main","web","api")) {
        $t = Get-SlhTarget $name
        $marker = if ($active -eq $name) { "*" } else { " " }
        Write-Host ("{0} {1,-6} {2,-12} {3,-22} {4}" -f $marker,$name.ToUpper(),$t.label,$t.railway_project,$t.service)
    }
    Show-Railway -Name $active
    Show-TargetIntegrity -Name $active
    Show-HeartbeatStatus -Name $active
    Write-SlhTitle "COMMANDS"
    Write-Host "slh                 -> Control Tower"
    Write-Host "slhstatus           -> Git + Railway + PC"
    Write-Host "slhmap              -> architecture / source-of-truth"
    Write-Host "slhwatch            -> health audit"
    Write-Host "slhpc               -> PC agent + heartbeat"
    Write-Host "slhsync             -> git fetch + runtime check"
    Write-Host "slhuse main|web|api -> switch Railway target"
    Write-Host "slhlogs             -> selected Railway logs"
    Write-Host "slhdeploycheck      -> selected deployment"
    Write-Host "slhredeploy -Force  -> explicit Railway redeploy"
    Write-Host "slhvarnames         -> variable names only"
    Write-Host "slhdoctor           -> target integrity + PC heartbeat"
}

function Show-Status {
    Show-SlhBanner
    Show-GitSummary
    Show-Railway -Name (Get-ActiveTargetName)
    Show-TargetIntegrity -Name (Get-ActiveTargetName)
    Show-HeartbeatStatus -Name (Get-ActiveTargetName)
    Show-PcSummary
}

function Show-Map {
    Show-SlhBanner
    Write-SlhTitle "SOURCE OF TRUTH"
    Write-Host "GitHub  = versioned code / PR / CI / release history"
    Write-Host "Railway = live deployment / runtime / infrastructure"
    Write-Host "Bot DB  = state/db.json on Railway Volume"
    Write-Host "API DB  = slh-api / Postgres data plane"
    Write-Host "PC      = local operator + PC_Osif2 agent"
    Write-SlhTitle "FLOW"
    Write-Host "PowerShell Control Tower -> Git / PR / CI -> Railway targets -> Telegram / Mini App / API"
    Write-Host "PowerShell Control Tower -> PC_Osif2 heartbeat / agent"
    Write-Host "No financial/token mutation is performed by this tool."
}

function Show-Watch {
    Show-SlhBanner
    Require-Command git
    Require-Command python
    Require-Command railway

    Write-SlhTitle "GIT CHECK"
    & git -C $RepoRoot diff --check
    $gitOk = ($LASTEXITCODE -eq 0)
    Write-Host $(if ($gitOk) { "PASS: git diff --check" } else { "FAIL: git diff --check" }) -ForegroundColor $(if ($gitOk) { "Green" } else { "Red" })

    Write-SlhTitle "PYTHON CHECK"
    & python -m compileall -q (Join-Path $RepoRoot "core") (Join-Path $RepoRoot "handlers")
    $pyOk = ($LASTEXITCODE -eq 0)
    Write-Host $(if ($pyOk) { "PASS: Python compileall" } else { "FAIL: Python compileall" }) -ForegroundColor $(if ($pyOk) { "Green" } else { "Red" })

    Show-PcSummary
    Show-Railway -Name (Get-ActiveTargetName)
}

function Show-Journal {
    Write-SlhTitle "JOURNAL"
    $dbPath = Join-Path $RepoRoot "state\db.json"
    if (-not (Test-Path $dbPath)) {
        Write-Host "Local state not mounted. Runtime /journal remains canonical." -ForegroundColor Yellow
        return
    }
    $db = $dbPath.Replace("\","\\")
    & python -c "import json; from pathlib import Path; d=json.loads(Path(r'$db').read_text(encoding='utf-8')); r=d.get('journal',[]); r=list(r.values()) if isinstance(r,dict) else r; [print(x) for x in r[-10:]]; print('Journal rows:',len(r))"
}

function Show-Tasks {
    Write-SlhTitle "TASKS"
    $dbPath = Join-Path $RepoRoot "state\db.json"
    if (-not (Test-Path $dbPath)) {
        Write-Host "Local state not mounted. Runtime /tasks remains canonical." -ForegroundColor Yellow
        return
    }
    $db = $dbPath.Replace("\","\\")
    & python -c "import json; from pathlib import Path; d=json.loads(Path(r'$db').read_text(encoding='utf-8')); t=d.get('tasks',{}); a=list(t.items()) if isinstance(t,dict) else list(enumerate(t if isinstance(t,list) else [])); [print(k,v) for k,v in a[-15:]]; print('Task rows:',len(a))"
}

function Sync-Check {
    Require-Command git
    Require-Command railway
    Write-SlhTitle "SYNC"
    Invoke-SlhGit fetch origin
    Show-GitSummary
    Show-Railway -Name (Get-ActiveTargetName)
    Write-Host "No automatic pull/push/merge/deploy/financial mutation." -ForegroundColor Green
}

function Show-Logs {
    Require-Command railway
    $name = Get-ActiveTargetName
    Ensure-SlhTarget $name
    $t = Get-SlhTarget $name
    Write-SlhTitle "$($t.label) / LOGS"
    & railway logs
}

function Show-DeployCheck {
    Require-Command railway
    $name = Get-ActiveTargetName
    Ensure-SlhTarget $name
    $t = Get-SlhTarget $name
    Write-SlhTitle "$($t.label) / DEPLOYMENT"
    & railway status
}

function Show-VariableNames {
    Require-Command railway
    Ensure-SlhTarget (Get-ActiveTargetName)
    Write-SlhTitle "VARIABLE NAMES"
    Write-Host "Names only; values are never printed." -ForegroundColor Green
    $raw = & railway variable list --json
    if ($LASTEXITCODE -ne 0) { throw "railway variable list failed" }
    try {
        $obj = $raw | ConvertFrom-Json
        if ($obj.variables) { $obj.variables.PSObject.Properties.Name | Sort-Object | ForEach-Object { Write-Host $_ } }
    } catch {
        Write-Host "Could not parse variable names safely." -ForegroundColor Yellow
    }
}

function Set-ActiveTarget {
    param([string]$Name)
    if ([string]::IsNullOrWhiteSpace($Name)) { throw "Usage: slhuse main|web|api" }
    $t = Get-SlhTarget $Name
    Require-Command railway
    if (-not (Test-Path $LocalControlDir)) { New-Item -ItemType Directory -Path $LocalControlDir -Force | Out-Null }
    & railway link --workspace $Config.workspace_id --project $t.railway_project_id --environment $t.environment_id --service $t.service_id
    if ($LASTEXITCODE -ne 0) { throw "Railway link failed" }
    Set-Content -Path $ActiveTargetPath -Value $Name.ToLower() -Encoding ASCII
    Write-Host "ACTIVE TARGET: $($Name.ToLower())" -ForegroundColor Green
}

function Pull-Main {
    if (-not $Force) { Write-Host "Blocked by default. Use: slhpull -Force" -ForegroundColor Yellow; return }
    $dirty = @(git -C $RepoRoot status --porcelain)
    if ($dirty.Count -gt 0) { throw "Working tree is dirty. Refusing automatic pull." }
    Invoke-SlhGit fetch origin
    Invoke-SlhGit pull --ff-only origin main
    Write-Host "Local main fast-forwarded." -ForegroundColor Green
}

function Redeploy-Selected {
    if (-not $Force) { Write-Host "Blocked by default. Use: slhredeploy -Force" -ForegroundColor Yellow; return }
    Require-Command railway
    $name = Get-ActiveTargetName
    Ensure-SlhTarget $name
    $t = Get-SlhTarget $name
    Write-Host "Redeploying $($t.railway_project) / $($t.service)..." -ForegroundColor Yellow
    & railway redeploy
    if ($LASTEXITCODE -ne 0) { throw "Railway redeploy failed" }
}

function Show-Doctor {
    Show-SlhBanner
    Show-TargetIntegrity -Name (Get-ActiveTargetName)
    Show-HeartbeatStatus -Name (Get-ActiveTargetName)
}

function Show-Help {
    Show-SlhBanner
    Write-Host ""
    Write-Host "slh                  Control Tower"
    Write-Host "slhstatus            Git + Railway + PC"
    Write-Host "slhmap               architecture / source-of-truth"
    Write-Host "slhwatch             health audit"
    Write-Host "slhpc                local PC agent"
    Write-Host "slhsync              sync check (read-only)"
    Write-Host "slhuse main|web|api  switch Railway target"
    Write-Host "slhlogs              recent Railway logs"
    Write-Host "slhdeploycheck       Railway deployment status"
    Write-Host "slhredeploy -Force   explicit redeploy"
    Write-Host "slhvarnames          variable names only"
    Write-Host "slhpull -Force       fast-forward local main"
    Write-Host "slhdoctor            target integrity + PC heartbeat"
}

switch ($Command) {
    "dashboard" { Show-Dashboard }
    "status" { Show-Status }
    "map" { Show-Map }
    "watch" { Show-Watch }
    "journal" { Show-Journal }
    "tasks" { Show-Tasks }
    "sync" { Sync-Check }
    "pc" { Show-PcSummary }
    "logs" { Show-Logs }
    "deploycheck" { Show-DeployCheck }
    "varnames" { Show-VariableNames }
    "use" { Set-ActiveTarget -Name $Target }
    "pull" { Pull-Main }
    "redeploy" { Redeploy-Selected }
    "doctor" { Show-Doctor }
    "help" { Show-Help }
    default { Show-Help }
}
