param(
    [ValidateSet("dashboard","status","map","watch","journal","tasks","sync","pc","logs","deploycheck","varnames","use","pull","redeploy","help")]
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
    $status = @(git -C $RepoRoot status --porcelain)
    $tracked = @($status | Where-Object { $_.Length -ge 2 -and $_.Substring(0,2) -ne "??" })
    $untracked = @($status | Where-Object { $_.Length -ge 2 -and $_.Substring(0,2) -eq "??" })

    Write-Host "Branch           : $branch"
    Write-Host "HEAD             : $head"
    Write-Host "Origin           : $(if ($origin) { $origin } else { 'unavailable' })"
    Write-Host "Tracked changes  : $($tracked.Count)"

    if ($tracked.Count -eq 0) {
        Write-Host "Git code         : CLEAN" -ForegroundColor Green
    } else {
        Write-Host "Git code         : MODIFIED" -ForegroundColor Yellow
        $tracked | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }
        if ($tracked.Count -gt 10) {
            Write-Host "  ... and $($tracked.Count - 10) more"
        }
    }

    Write-Host "Local workspace  : $($untracked.Count) untracked item(s)" -ForegroundColor DarkCyan
    if ($untracked.Count -gt 0) {
        $untracked | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }
        if ($untracked.Count -gt 10) {
            Write-Host "  ... and $($untracked.Count - 10) more"
        }
    }
}
function Get-LocalAgentSupervisorProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*slh_agent_background.ps1*" }
}

function Get-SlhPcTask {
    Get-ScheduledTask -TaskName "SLH-PC-Agent" -ErrorAction SilentlyContinue
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
        if ($heartbeat) {
            Write-Host "Heartbeat code: PRESENT" -ForegroundColor Green
        } else {
            Write-Host "Heartbeat code: MISSING" -ForegroundColor Red
        }
    } else {
        Write-Host "Agent file: MISSING" -ForegroundColor Red
    }

    if (Test-Path $secretPath) {
        $len = (Get-Content $secretPath -Raw -Encoding ASCII).Trim().Length
        Write-Host "Heartbeat secret: PRESENT (length $len)" -ForegroundColor Green
    } else {
        Write-Host "Heartbeat secret: MISSING" -ForegroundColor Red
    }

    $task = Get-SlhPcTask
    $supervisors = @(Get-LocalAgentSupervisorProcesses)
    $agents = @(Get-LocalAgentProcesses)

    if ($task) {
        Write-Host "Task        : $($task.State)"
    } else {
        Write-Host "Task        : NOT FOUND" -ForegroundColor Red
    }

    if ($supervisors.Count -eq 1) {
        $supervisor = $supervisors[0]
        Write-Host "Supervisor  : RUNNING (PID $($supervisor.ProcessId))" -ForegroundColor Green
    } elseif ($supervisors.Count -gt 1) {
        $supervisor = $null
        $pids = ($supervisors | ForEach-Object { $_.ProcessId }) -join ", "
        Write-Host "Supervisor  : AMBIGUOUS ($($supervisors.Count)) PIDs: $pids" -ForegroundColor Yellow
    } else {
        $supervisor = $null
        Write-Host "Supervisor  : NOT RUNNING" -ForegroundColor Red
    }

    if ($agents.Count -eq 1) {
        $agent = $agents[0]
        Write-Host "Agent       : RUNNING (PID $($agent.ProcessId))" -ForegroundColor Green

        if ($supervisor -and ([int]$agent.ParentProcessId -eq [int]$supervisor.ProcessId)) {
            Write-Host "Parent      : SUPERVISOR (PID $($supervisor.ProcessId))" -ForegroundColor Green
            Write-Host "Chain       : HEALTHY" -ForegroundColor Green
        } elseif ($supervisor) {
            Write-Host "Parent      : MISMATCH (PID $($agent.ParentProcessId))" -ForegroundColor Yellow
            Write-Host "Chain       : BROKEN" -ForegroundColor Red
        } else {
            Write-Host "Parent      : UNSUPERVISED (PID $($agent.ParentProcessId))" -ForegroundColor Yellow
            Write-Host "Chain       : BROKEN" -ForegroundColor Red
        }
    } elseif ($agents.Count -gt 1) {
        $pids = ($agents | ForEach-Object { $_.ProcessId }) -join ", "
        Write-Host "Agent       : AMBIGUOUS ($($agents.Count)) PIDs: $pids" -ForegroundColor Yellow
        Write-Host "Parent      : NOT DETERMINED" -ForegroundColor Yellow
        Write-Host "Chain       : AMBIGUOUS" -ForegroundColor Yellow
    } else {
        Write-Host "Agent       : NOT RUNNING" -ForegroundColor Yellow

        if ($supervisor) {
            Write-Host "Parent      : SUPERVISOR HAS NO AGENT" -ForegroundColor Yellow
            Write-Host "Chain       : DEGRADED" -ForegroundColor Yellow
        } else {
            Write-Host "Parent      : NONE"
            Write-Host "Chain       : DOWN" -ForegroundColor Red
        }
    }
}
function Show-Railway {
    param([string]$Name)
    Require-Command railway
    # READ-ONLY: target switching is performed only by slhuse.
    $t = Get-SlhTarget $Name
    Write-SlhTitle "$($t.label) / Railway"
    Write-Host "Project : $($t.railway_project)"
    Write-Host "Service : $($t.service)"
    Write-Host "Env     : $($t.environment)"
    Write-Host "Role    : $($t.role)"
    & railway status `
        --project $t.railway_project_id `
        --environment $t.environment_id
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Railway status returned exit code $LASTEXITCODE" -ForegroundColor Yellow
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
    Write-SlhTitle "COMMANDS"
    Write-Host "slh                 -> Control Tower"
    Write-Host "slhstatus           -> Git + Railway + PC"
    Write-Host "slhmap              -> architecture / source-of-truth"
    Write-Host "slhwatch            -> health audit"
    Write-Host "slhpc               -> PC agent + heartbeat"
    Write-Host "slhsync             -> sync check (read-only)"
    Write-Host "slhuse main|web|api -> switch Railway target"
    Write-Host "slhlogs             -> selected Railway logs"
    Write-Host "slhdeploycheck      -> selected deployment"
    Write-Host "slhredeploy -Force  -> explicit Railway redeploy"
    Write-Host "slhvarnames         -> variable names only"
}

function Show-Status {
    Show-SlhBanner
    Show-GitSummary
    Show-Railway -Name (Get-ActiveTargetName)
    Show-PcSummary
}

function Show-Map {
    Show-SlhBanner
    Write-SlhTitle "SOURCE OF TRUTH"
    Write-Host "GitHub  = versioned code / PR / CI / release history"
    Write-Host "Railway = live deployment / runtime / infrastructure"
    Write-Host "Bot DB  = /app/state/db.json on MAIN BOT Railway Volume"
    Write-Host "Journal = /app/state/journals/*.jsonl on MAIN BOT Railway Volume"
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
    Require-Command railway

    # Canonical journal lives on the MAIN BOT Railway Volume.
    $t = Get-SlhTarget "main"

    Write-SlhTitle "JOURNAL / MAIN BOT"

    $py = "import glob,json; entries=[json.loads(line) for f in glob.glob('/app/state/journals/*.jsonl') for line in open(f,encoding='utf-8') if line.strip()]; entries.sort(key=lambda x:str(x.get('timestamp',x.get('time','')))); print('Remote journal: no entries') if not entries else [print(json.dumps(x,ensure_ascii=False)) for x in entries[-10:]]; print('Journal rows:',len(entries))"

    & railway ssh `
        --project $t.railway_project_id `
        --service $t.service_id `
        --environment $t.environment_id `
        -- python3 -c $py

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Remote journal read failed." -ForegroundColor Yellow
    }
}
function Show-Tasks {
    Require-Command railway

    # Canonical tasks live in the MAIN BOT Railway Volume.
    $t = Get-SlhTarget "main"

    Write-SlhTitle "TASKS / MAIN BOT"

    $py = "import json; d=json.load(open('/app/state/db.json',encoding='utf-8')); t=d.get('tasks',{}); print('REMOTE TASKS'); [print(k,'|',v.get('status','active'),'|',v.get('progress',0),'%','|',v.get('title',v.get('desc','?'))) for k,v in t.items()]; print('Task rows:',len(t))"

    & railway ssh `
        --project $t.railway_project_id `
        --service $t.service_id `
        --environment $t.environment_id `
        -- python3 -c $py

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Remote tasks read failed." -ForegroundColor Yellow
    }
}
function Sync-Check {
    Require-Command git
    Require-Command railway

    Show-SlhBanner
    Write-SlhTitle "SYNC / READ-ONLY"

    $localSha = (git -C $RepoRoot rev-parse HEAD).Trim()

    if (-not $localSha) {
        throw "Could not determine local HEAD."
    }

    $remoteLine = (git -C $RepoRoot ls-remote origin refs/heads/main).Trim()

    if (-not $remoteLine) {
        throw "Could not read origin/main."
    }

    $remoteSha = ($remoteLine -split "\s+")[0]

    Write-Host "Local HEAD  : $localSha"
    Write-Host "Remote main : $remoteSha"

    if ($localSha -eq $remoteSha) {
        Write-Host "Git sync    : IN SYNC" -ForegroundColor Green
    } else {
        Write-Host "Git sync    : DIFFERENT" -ForegroundColor Yellow
    }

    Show-GitSummary
    Show-Railway -Name (Get-ActiveTargetName)

    Write-Host "No fetch/pull/push/merge/deploy/financial mutation." -ForegroundColor Green
}
function Show-Logs {
    Require-Command railway
    $name = Get-ActiveTargetName
    # READ-ONLY: target switching is performed only by slhuse.
    $t = Get-SlhTarget $name
    Write-SlhTitle "$($t.label) / LOGS"
    & railway logs `
        --project $t.railway_project_id `
        --environment $t.environment_id `
        --service $t.service_id
}

function Show-DeployCheck {
    Require-Command railway
    $name = Get-ActiveTargetName
    # READ-ONLY: target switching is performed only by slhuse.
    $t = Get-SlhTarget $name
    Write-SlhTitle "$($t.label) / DEPLOYMENT"
    & railway deployment list `
        --service $t.service_id `
        --environment $t.environment_id `
        --limit 5
}

function Show-VariableNames {
    Require-Command railway
    # READ-ONLY: target switching is performed only by slhuse.
    $name = Get-ActiveTargetName
    $t = Get-SlhTarget $name
    Write-SlhTitle "VARIABLE NAMES"
    Write-Host "Names only; values are never printed." -ForegroundColor Green

    $raw = & railway variable list `
        --service $t.service_id `
        --environment $t.environment_id `
        --json

    if ($LASTEXITCODE -ne 0) {
        throw "railway variable list failed"
    }

    try {
        $obj = ($raw -join "`n") | ConvertFrom-Json

        $names = @(
            $obj.PSObject.Properties.Name |
                Sort-Object
        )

        Write-Host "Variable count: $($names.Count)" -ForegroundColor Green

        $names | ForEach-Object {
            Write-Host $_
        }
    }
    catch {
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
    "help" { Show-Help }
    default { Show-Help }
}