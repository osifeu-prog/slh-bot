#!/bin/bash
cd ~/slh_clean
echo ""
echo "  ██████╗ ██╗     ██╗  ██╗"
echo "  ██╔════╝ ██║     ██║  ██║"
echo "  ███████╗ ██║     ███████║"
echo "  ╚════██║ ██║     ██╔══██║"
echo "  ███████║ ███████╗██║  ██║"
echo "  ╚══════╝ ╚══════╝╚═╝  ╚═╝"
echo ""
echo "🔍 Checking Python syntax..."
if python3 -m py_compile handlers/loader.py && python3 -m py_compile bot_stable.py; then
    echo "✅ Syntax OK – starting bot"
    for i in 10 20 30 40 50 60 70 80 90 100; do
        echo "Loading... ($i%)"
        sleep 0.2
    done
    pkill -f bot_stable.py 2>/dev/null
    sleep 1
    nohup python3 -u -B bot_stable.py > bot.log 2>&1 &
    sleep 2
    pgrep -af bot_stable.py && echo "✅ Bot is running" || echo "❌ Start failed"
else
    echo "❌ Syntax error – bot NOT started"
    exit 1
fi
