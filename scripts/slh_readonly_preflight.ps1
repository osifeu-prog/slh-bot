# SLH read-only local preflight
# Collects a single JSON report. Does not start/stop processes or modify SLH state.
$ErrorActionPreference = "SilentlyContinue"

$now = Get-Date
$homeDir = $env:USERPROFILE
$agentFile = Join-Path $homeDir "slh_agent.py"
$launcherFile = Join-Path $homeDir "slh_agent.bat"
$runnerFile = Join-Path $homeDir "slh_agent_background.ps1"
$agentLog = Join-Path $homeDir "slh_agent.log"
$runnerLog = Join-Path $homeDir "slh_agent_background.log"

function Get-FileEvidence([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $item = Get-Item -LiteralPath $Path
        return [ordered]@{
            exists = $true
            length_bytes = $item.Length
            last_write_time = $item.LastWriteTime.ToString("o")
            age_minutes = [math]::Round(($now - $item.LastWriteTime).TotalMinutes, 2)
        }
    }
    return [ordered]@{ exists = $false }
}

$allProcesses = @(Get-CimInstance Win32_Process)
$agentProcesses = @($allProcesses | Where-Object {
    $_.Name -match '^(python|pythonw)(\.exe)?$' -and
    $_.CommandLine -match '(?i)slh_agent\.py'
})
$runnerProcesses = @($allProcesses | Where-Object {
    $_.Name -match '^(powershell|pwsh)(\.exe)?$' -and
    $_.CommandLine -match '(?i)slh_agent_background\.ps1'
})

$processEvidence = foreach ($proc in $agentProcesses) {
    $parent = $allProcesses | Where-Object { $_.ProcessId -eq $proc.ParentProcessId } | Select-Object -First 1
    $grandparent = $null
    if ($parent) {
        $grandparent = $allProcesses | Where-Object { $_.ProcessId -eq $parent.ParentProcessId } | Select-Object -First 1
    }
    [ordered]@{
        pid = [int]$proc.ProcessId
        parent_pid = [int]$proc.ParentProcessId
        process_name = $proc.Name
        created = if ($proc.CreationDate) { ([datetime]$proc.CreationDate).ToString("o") } else { $null }
        parent_exists = [bool]$parent
        parent_name = if ($parent) { $parent.Name } else { $null }
        grandparent_pid = if ($parent) { [int]$parent.ParentProcessId } else { $null }
        grandparent_exists = [bool]$grandparent
        ancestry_status = if (-not $parent) { "PARENT_MISSING" } elseif (-not $grandparent) { "GRANDPARENT_MISSING" } else { "ANCESTRY_PRESENT" }
    }
}

$scheduledTasks = @()
$taskCmd = Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue
if ($taskCmd) {
    $scheduledTasks = @(Get-ScheduledTask | Where-Object {
        $_.TaskName -match '(?i)SLH|agent|heartbeat|watchdog|supervisor' -or
        $_.TaskPath -match '(?i)SLH|agent'
    } | ForEach-Object {
        [ordered]@{ name = $_.TaskName; path = $_.TaskPath; state = [string]$_.State }
    })
}

$startupEntries = @()
$startupPath = [Environment]::GetFolderPath("Startup")
if ($startupPath -and (Test-Path $startupPath)) {
    $startupEntries = @(Get-ChildItem -LiteralPath $startupPath -File | Where-Object {
        $_.Name -match '(?i)SLH|agent|heartbeat|watchdog'
    } | ForEach-Object {
        [ordered]@{ name = $_.Name; last_write_time = $_.LastWriteTime.ToString("o") }
    })
}

$report = [ordered]@{
    schema = "slh.readonly-preflight.v1"
    generated_at = $now.ToString("o")
    machine = $env:COMPUTERNAME
    scope = "LOCAL_DIAGNOSTICS_ONLY"
    safety = [ordered]@{
        changed_application_state = $false
        started_or_stopped_processes = $false
        read_secret_contents = $false
        read_log_contents = $false
    }
    agent_files = [ordered]@{
        agent = Get-FileEvidence $agentFile
        launcher = Get-FileEvidence $launcherFile
        background_runner = Get-FileEvidence $runnerFile
        agent_log = Get-FileEvidence $agentLog
        background_log = Get-FileEvidence $runnerLog
    }
    process_check = [ordered]@{
        agent_process_count = $agentProcesses.Count
        agent_processes = @($processEvidence)
        background_runner_process_count = $runnerProcesses.Count
        background_runner_detected = ($runnerProcesses.Count -gt 0)
        assessment = if ($agentProcesses.Count -eq 0) { "AGENT_NOT_DETECTED" } elseif ($runnerProcesses.Count -eq 0) { "AGENT_RUNNING_RUNNER_NOT_DETECTED" } elseif (@($processEvidence | Where-Object { $_.ancestry_status -ne "ANCESTRY_PRESENT" }).Count -gt 0) { "PROCESS_ANCESTRY_WARNING" } else { "PROCESSES_DETECTED_REQUIRES_HEARTBEAT_VALIDATION" }
    }
    scheduled_tasks = @($scheduledTasks)
    startup_entries = @($startupEntries)
    limitations = @(
        "A process and fresh log timestamp do not prove that the remote heartbeat is accepted.",
        "This report does not read Railway volume data or validate Credits ledger continuity.",
        "No trading-gate or release decision is made by this local-only script."
    )
}

$stamp = $now.ToString("yyyyMMdd_HHmmss")
$outPath = Join-Path $homeDir "SLH_READONLY_PREFLIGHT_$stamp.json"
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outPath -Encoding UTF8

Write-Host ""
Write-Host "SLH READ-ONLY PREFLIGHT COMPLETE"
Write-Host ("Assessment: " + $report.process_check.assessment)
Write-Host ("Agent processes: " + $report.process_check.agent_process_count)
Write-Host ("Background runner detected: " + $report.process_check.background_runner_detected)
Write-Host ("Scheduled task matches: " + $scheduledTasks.Count)
Write-Host ("Report: " + $outPath)
Write-Host "No SLH state, processes, deployments, or trading gates were changed."
