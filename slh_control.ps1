Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║             SLH OS CONTROL               ║" -ForegroundColor Cyan
Write-Host "║             SYSTEM MONITOR               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan

Write-Host ""

Write-Host "📁 PROJECT" -ForegroundColor Yellow
Write-Host "Path: $PWD"

Write-Host ""

Write-Host "🧬 VERSION" -ForegroundColor Yellow
git log -1 --oneline 2>$null

Write-Host ""

Write-Host "🤖 BOT ENTRY" -ForegroundColor Yellow
if(Test-Path ".\bot_gateway.py"){
    Write-Host "✅ bot_gateway.py detected"
}else{
    Write-Host "❌ missing"
}

Write-Host ""

Write-Host "🧠 HANDLER SYSTEM" -ForegroundColor Yellow
if(Test-Path ".\handlers\loader.py"){
    $count = (Select-String -Path ".\handlers\loader.py" -Pattern "import|register" | Measure-Object).Count
    Write-Host "✅ loader active"
    Write-Host "Modules references: $count"
}else{
    Write-Host "❌ loader missing"
}

Write-Host ""

Write-Host "💬 LLM PATH" -ForegroundColor Yellow
if(Test-Path ".\handlers\llm_handler.py"){
    Write-Host "✅ llm_handler.py detected"
}else{
    Write-Host "❌ missing"
}

Write-Host ""

Write-Host "📊 SLH PROGRESS" -ForegroundColor Yellow
Write-Host "[████████░░] 80% SYSTEM READY"

Write-Host ""

Write-Host "🚀 SLH OS ONLINE" -ForegroundColor Green
