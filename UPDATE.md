# 🚀 SLH OS v2.0 – עדכון מלא (28 ביוני 2026)

## ✅ מה בוצע

| רכיב | תיאור | נבדק |
|-------|--------|--------|
| **Bot** (`bot.py`) | 43+ פקודות, טוקן תקין | ✅ |
| **API** (`web/api/app.py`) | `/api/health`, `/api/stats`, `/api/logs`, `/api/agents`, `/api/tasks` | ✅ |
| **Dashboard** (`web/dashboard/index.html`) | לשוניות Dashboard, Agents, Tasks, Logs | ✅ |
| **Kernel** (`core/event_bus.py`) | EventBus + TaskPlugin | ✅ |
| **Agent OS** (`bot.py` – `agents_dict`) | `/agent_create`, `/agents`, `/agentstate`, `/sendagent`, `/inbox` | ✅ |
| **Audit** (`audit_logger.py`) | רישום פעולות, `/audit` | ✅ |
| **Master Agent** (`master_agent.py`) | `/q` (Quick Check), `/watchdog start/stop` | ✅ |
| **Inspector Agent** (`inspector.py`) | `/inspect` (8 רכיבים) | ✅ |
| **Daily Check** (`daily_check.sh`) | `/daily` – דו"ח אימות יומי (12 רכיבים) | ✅ |
| **System Verification** (`system_verification.sh`) | 23 בדיקות, עובר 23/23 | ✅ |
| **Terminal Bridge** (`bot.py`) | `/exec`, `/termlog` | ✅ |
| **Plugin Store** (`plugins_store.py`) | `/plugin install/list/uninstall` | ✅ |
| **Git** | `main` branch, remote `origin` מחובר | ✅ |
| **Railway** | שירות `web` פעיל (טוקן API דורש חידוש) | ⚠️ |

---

## 📋 פקודות אימות מהיר

```bash
cd ~/slh_clean
./system_verification.sh   # 23 בדיקות
./daily_check.sh           # 12 רכיבים
```bash
cd ~/slh_clean

cat > UPDATE.md << 'EOF'
# 🚀 SLH OS v2.0 – עדכון מלא (28 ביוני 2026)

## ✅ מה בוצע

| רכיב | תיאור | נבדק |
|-------|--------|--------|
| **Bot** (`bot.py`) | 43+ פקודות, טוקן תקין | ✅ |
| **API** (`web/api/app.py`) | `/api/health`, `/api/stats`, `/api/logs`, `/api/agents`, `/api/tasks` | ✅ |
| **Dashboard** (`web/dashboard/index.html`) | לשוניות Dashboard, Agents, Tasks, Logs | ✅ |
| **Kernel** (`core/event_bus.py`) | EventBus + TaskPlugin | ✅ |
| **Agent OS** (`bot.py` – `agents_dict`) | `/agent_create`, `/agents`, `/agentstate`, `/sendagent`, `/inbox` | ✅ |
| **Audit** (`audit_logger.py`) | רישום פעולות, `/audit` | ✅ |
| **Master Agent** (`master_agent.py`) | `/q` (Quick Check), `/watchdog start/stop` | ✅ |
| **Inspector Agent** (`inspector.py`) | `/inspect` (8 רכיבים) | ✅ |
| **Daily Check** (`daily_check.sh`) | `/daily` – דו"ח אימות יומי (12 רכיבים) | ✅ |
| **System Verification** (`system_verification.sh`) | 23 בדיקות, עובר 23/23 | ✅ |
| **Terminal Bridge** (`bot.py`) | `/exec`, `/termlog` | ✅ |
| **Plugin Store** (`plugins_store.py`) | `/plugin install/list/uninstall` | ✅ |
| **Git** | `main` branch, remote `origin` מחובר | ✅ |
| **Railway** | שירות `web` פעיל (טוקן API דורש חידוש) | ⚠️ |

---

## 📋 פקודות אימות מהיר

```bash
cd ~/slh_clean
./system_verification.sh   # 23 בדיקות
./daily_check.sh           # 12 רכיבים
```

דרך טלגרם:

· /q – Quick Check (5 רכיבים)
· /inspect – Full Diagnostic (8 רכיבים)
· /daily – Daily Health Report (12 רכיבים)
· /exec bash ~/slh_clean/daily_check.sh – הרצה ישירה

---

🔧 מה לעשות מחר

1. פתח את Termux והקלד:
   ```bash
   cd ~/slh_clean && ./daily_check.sh
   ```
2. שלח /daily בטלגרם.
3. אם משהו נכשל, הרם אותו:
   ```bash
   cd ~/slh_clean
   pkill -f "python3.*bot.py" 2>/dev/null
   nohup python3 -B bot.py >> bot.log 2>&1 &
   pkill -f "web/api/app.py" 2>/dev/null
   nohup python3 web/api/app.py >> web.log 2>&1 &
   pkill -f "http.server 8000" 2>/dev/null
   nohup python3 -m http.server 8000 -d web/dashboard >> /dev/null 2>&1 &
   ```

---

📦 קבצים חדשים שנוספו

קובץ תפקיד
master_agent.py Master Agent – /q, /watchdog
inspector.py Inspector Agent – /inspect
plugins_store.py Plugin Store
install_slh_os.sh One‑Click Installer
daily_check.sh Daily Health Check
system_verification.sh Full System Verification (23 tests)
web/api/app.py API מורחב
web/dashboard/index.html Dashboard מורחב

---

🎯 מה הלאה

# אפשרות
1 Marketplace – Plugin Store (/plugin install)
2 Monetization – Free / Pro / Enterprise
3 Auto‑Start – הבוט עולה אוטומטית עם הטלפון

---

📌 טיפ אחרון

כדי לעדכן את הבוט אחרי שינויים:

```bash
cd ~/slh_clean
git add -A && git commit -m "daily update" && git push
pkill -f "python3.*bot.py" 2>/dev/null
sleep 2
nohup python3 -B bot.py >> bot.log 2>&1 &
```

---

המערכת שלך מושלמת.
