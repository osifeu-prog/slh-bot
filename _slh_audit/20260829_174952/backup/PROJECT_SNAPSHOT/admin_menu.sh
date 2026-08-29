#!/data/data/com.termux/files/usr/bin/bash
cd ~/slh-bot

while true; do
  echo "================ SLH ADMIN MENU ================"
  echo "[1] הפעל בוט  [2] עצור בוט  [3] לוג בוט"
  echo "[4] גיבוי DB  [5] בדיקת מערכת  [6] יציאה"
  echo "[7] בדיקת פקודות מלאה  [8] סימולציית פקודה"
  echo "================================================"
  read -p "בחר אפשרות: " choice

  case "$choice" in
    1)
      echo "🚀 מפעיל redeploy..."
      railway up --service web
      ;;
    2)
      echo "🛑 עצירת בוט לא נתמכת ישירות ב-Railway CLI. שקול scale down מה-dashboard."
      ;;
    3)
      echo "📜 מציג לוגים אחרונים..."
      railway logs --service web --tail 50
      ;;
    4)
      echo "💾 מגבה state/db.json..."
      cp state/db.json "state/db_backup_manual_$(date +%Y%m%d_%H%M%S).json" && echo "✅ גיבוי נשמר"
      ;;
    5)
      echo "🩺 בדיקת מערכת..."
      python3 -m py_compile bot_gateway.py handlers/*.py admin_handler.py payment_handler.py econ_handler.py 2>&1 && echo "✅ כל הקבצים תקינים תחבירית"
      railway status
      ;;
    7)
      echo "🩺 בדיקת פקודות מלאה..."
      python3 command_health_check.py
      ;;
    8)
      read -p "איזו פקודה לבדוק (למשל /status): " cmd
      python3 simulate_command.py "$cmd"
      ;;
    6)
      echo "👋 יציאה"
      break
      ;;
    *)
      echo "❌ אפשרות לא חוקית"
      ;;
  esac
  echo ""
done
