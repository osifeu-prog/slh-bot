Write-Host "=== SLH ONE SHOT AUDIT ==="

Write-Host ""
Write-Host "1 COMPILE"
python -m compileall -q .
if ($LASTEXITCODE -eq 0) { Write-Host "OK COMPILE" } else { Write-Host "FAIL COMPILE" }

Write-Host ""
Write-Host "2 IMPORTS"

python -c "
import importlib
mods=[
'handlers.loader',
'handlers.payment_handler',
'econ_handler',
'handlers.llm_handler',
'handlers.askdebug_handler'
]

for m in mods:
    try:
        x=importlib.import_module(m)
        print('OK',m,'register=',hasattr(x,'register'))
    except Exception as e:
        print('FAIL',m,e)
"

Write-Host ""
Write-Host "3 MARKDOWN ACTIVE FILES"

git grep "parse_mode.*Markdown" -- '*.py' |
Select-String -NotMatch "bak|backup|disabled"

Write-Host ""
Write-Host "4 RAILWAY TELEGRAM ERRORS"

railway logs --lines 200 |
Select-String "can't parse entities|ERROR|Exception|Traceback"

Write-Host ""
Write-Host "=== END AUDIT ==="
