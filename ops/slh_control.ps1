# Canonical SLH PowerShell controls. Read-only by default.
$script:SLH_ROOT = if ($env:SLH_ROOT) { $env:SLH_ROOT } else { 'C:\Users\USER\slh-bot-clean' }

function slhroot { Set-Location -LiteralPath $script:SLH_ROOT }

function slhpc {
    slhroot
    Write-Host '=== SLH PC ===' -ForegroundColor Cyan
    Write-Host ('Computer: ' + $env:COMPUTERNAME)
    $agent=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'slh_agent\.py' } | Select-Object -First 1
    Write-Host ('SLH Agent: ' + $(if($agent){'RUNNING'}else{'NOT DETECTED'}))
    if(Get-Command ollama -ErrorAction SilentlyContinue){
        try{$r=Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5; Write-Host ('Ollama: OK | '+(@($r.models|ForEach-Object name)-join ', ')) -ForegroundColor Green}
        catch{Write-Host 'Ollama: OFFLINE' -ForegroundColor Yellow}
    }else{Write-Host 'Ollama: NOT INSTALLED' -ForegroundColor Yellow}
    Write-Host ('Cloudflared: '+$(if(Get-Command cloudflared -ErrorAction SilentlyContinue){'INSTALLED'}else{'NOT INSTALLED'}))
    Write-Host ('Docker: '+$(if(Get-Command docker -ErrorAction SilentlyContinue){'INSTALLED'}else{'NOT INSTALLED'}))
    Write-Host ('ADB: '+$(if(Get-Command adb -ErrorAction SilentlyContinue){'INSTALLED'}else{'NOT INSTALLED'}))
}

function slhbiz { slhroot; Write-Host '=== SLH BUSINESS CONTROL ===' -ForegroundColor Cyan; if(Get-Command railway -ErrorAction SilentlyContinue){railway status}; Write-Host ''; Write-Host 'Telegram: /biz /biz_users [days] /biz_revenue [days] /biz_ai /biz_bots' }
function slhusers { Write-Host 'Telegram MAIN: /biz_users [days]' }
function slhrevenue { Write-Host 'Telegram MAIN: /biz_revenue [days]' }
function slhbots { Write-Host 'Telegram MAIN: /biz_bots' }
function slhai { slhpc; Write-Host ''; Write-Host 'Telegram MAIN: /biz_ai' }
function slhsync { slhroot; git pull --ff-only; Write-Host 'SLH repository synchronized with origin/main.' }
function slhbusiness { slhbiz }
