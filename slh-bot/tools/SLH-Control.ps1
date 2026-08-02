Write-Host ""
Write-Host "███████╗██╗     ██╗  ██╗" -ForegroundColor Cyan
Write-Host "██╔════╝██║     ██║  ██║" -ForegroundColor Cyan
Write-Host "███████╗██║     ███████║" -ForegroundColor Cyan
Write-Host "╚════██║██║     ██╔══██║" -ForegroundColor Cyan
Write-Host "███████║███████╗██║  ██║" -ForegroundColor Cyan
Write-Host "╚══════╝╚══════╝╚═╝  ╚═╝" -ForegroundColor Cyan

Write-Host ""
Write-Host "        SLH OS CONTROL TOWER" -ForegroundColor Yellow
Write-Host "        MASTER SYNC PANEL" -ForegroundColor Yellow
Write-Host ""

Write-Host "===== ENV =====" -ForegroundColor Green
python --version
git branch --show-current

Write-Host ""
Write-Host "===== STATE =====" -ForegroundColor Green

python -c "import json; d=json.load(open('state/db.json',encoding='utf-8')); print('Agents:',len(d.get('agents',{}))); print('Tasks:',len(d.get('tasks',{}))); print('Users:',len(d.get('users',{})))"

Write-Host ""
Write-Host "===== ASK =====" -ForegroundColor Green

python -c "from core.ask_router import detect_intent; print('System intent:',detect_intent('מה מצב המערכת')); print('Agents intent:',detect_intent('כמה סוכנים יש במערכת'))"

Write-Host ""
Write-Host "===== GIT =====" -ForegroundColor Green
git status --short

Write-Host ""
Write-Host "===== END SLH CONTROL TOWER =====" -ForegroundColor Cyan
