# SLH ESP — Handoff Document
**תאריך:** 2026-09-14
**מחבר:** סשן פיתוח ESP32 + בוט + סוכן מקומי

## ארכיטקטורה

Telegram User
↓ /esp_flash /esp_compile /esp_sync /esp_msg /esp_view
Railway Bot (slh-bot-clean)
↓ MQTT publish → slh/esp/<DEVICE_ID>/command
↓ MQTT publish → slh/esp/<DEVICE_ID>/action
↓ MQTT publish → slh/agent/<AGENT_ID>/task
↓
ESP32 (COM9) Local Agent (PC)

WiFi + MQTT - pio, esptool, git

TFT ILI9341 320x240 - whitelist-only

Touch XPT2046 - runs at startup (VBS)

4 tabs, actions - logs to slh_agent.log

20s screensaver (eyes + hat)
↓ MQTT publish → slh/esp/<DEVICE_ID>/response
↓ MQTT publish → slh/esp/<DEVICE_ID>/heartbeat
↓ MQTT publish → slh/agent/<AGENT_ID>/result

text

## רכיבים

### ESP32 (ESP32_14335C6C32C0)
- **Board:** ESP32-D0WD-V3, 4MB flash, MAC 14:33:5c:6c:32:c0
- **Display:** ILI9341 320x240 SPI (MISO=12, MOSI=13, SCLK=14, CS=15, DC=2, RST=4, BL=21)
- **Touch:** XPT2046 (separate SPI: MOSI=32, MISO=39, CLK=25, CS=33, IRQ=36)
- **Firmware:** `C:\Users\USER\Desktop\APP 7625\ESP32_Text_Display_Project\src\main.cpp`
- **PlatformIO:** `platformio.ini` with TFT_eSPI + PubSubClient + XPT2046_Touchscreen
- **Features:**
  - 4 tabs: Wallet, Earn, Devices, Info
  - NTP clock (Asia/Jerusalem)
  - Screen saver: eyes + hat + crown (20s idle)
  - Touch actions: stake, invite, learn, sync
  - MQTT buffer 2048 bytes

### Local Agent
- **File:** `C:\Users\USER\slh_agent.py`
- **Launcher:** `C:\Users\USER\slh_agent.bat` (via VBS in Startup)
- **VBS:** `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\slh_agent.vbs`
- **Log:** `C:\Users\USER\slh_agent.log`
- **Agent ID:** `AGENT_OSIF2` (from hostname)
- **Topics:**
  - Task: `slh/agent/AGENT_OSIF2/task`
  - Result: `slh/agent/AGENT_OSIF2/result`
  - Status: `slh/agent/AGENT_OSIF2/status`
- **Whitelist actions:**
  - `esp.ports` → `python -m serial.tools.list_ports`
  - `esp.chip_id` → `esptool --port COM9 chip_id`
  - `esp.compile` → `pio run` in project dir
  - `esp.flash` → `pio run -t upload --upload-port COM9`
  - `git.status` → `git status --short`
  - `git.log` → `git log --oneline -5`

### Bot Handlers (new in this session)
- `handlers/esp_control.py` — `/esp_msg`, `/esp_led`, `/esp_reboot`, `/esp_clear`, `/esp_color`, `/esp_sync`, `/esp_view`, and action listener for device-initiated actions
- `handlers/esp_agent_control.py` — `/esp_flash`, `/esp_compile`, `/esp_ports`, `/esp_chipid`, `/agent_status`

### DB Records
- `state/devices.json` → `ESP32_14335C6C32C0` with `mqtt_topic: slh/esp/ESP32_14335C6C32C0`, `owner: 8789977826`
- `state/db.json` → `device_wallets`, `device_agent_map`, `esp_licenses`

## Commands Available

| Command | What it does | Where |
|---|---|---|
| `/esp_ping <device>` | Ping | MQTT |
| `/esp_sync <device>` | Push wallet data to screen | MQTT |
| `/esp_msg <device> <text>` | Show text | MQTT |
| `/esp_led <device> <pin> <0/1>` | GPIO control | MQTT |
| `/esp_clear <device>` | Clear to ready screen | MQTT |
| `/esp_reboot <device>` | Reboot ESP | MQTT |
| `/esp_view <device>` | ASCII view of screen | MQTT |
| `/esp_flash` | Flash firmware via agent | Agent |
| `/esp_compile` | Compile via agent | Agent |
| `/esp_ports` | List COM ports | Agent |
| `/esp_chipid` | Read chip info | Agent |
| `/agent_status` | Check agent online | Agent |

## Known Issues
- Screen saver blink animation is awkward (not critical, cosmetic)
- `/esp_view` shows zeros if called before first sync
- Autorefresh every 60s was removed (too many messages in Telegram)

## Next Steps (Planned)
1. Voting on screen (from `/propose` proposals)
2. AI Tamagotchi integration — needs spec
3. Skins system — themable via Telegram
4. `/esp_edit` — remote code editing via Telegram (advanced)

## Emergency Recovery
If ESP stuck:
1. Open Serial Monitor: `pio device monitor --port COM9 --baud 115200`
2. Press EN/RST button on board
3. If still stuck: `python -m esptool --port COM9 erase_flash` then `pio run -t upload`

If agent stopped:
1. Check `Get-Process python`
2. Restart: `Start-Process wscript.exe "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\slh_agent.vbs"`
3. Check log: `Get-Content C:\Users\USER\slh_agent.log -Tail 20`

If bot is silent:
1. `railway logs --service web 2>&1 | Select-String "ESP" | Select-Object -Last 20`
2. Restart from GitHub: `git push origin main` (Railway auto-deploys)
---

## Update — 2026-09-14 (Evening)

### מה נסגר היום

| רכיב | סטטוס |
|---|---|
| ESP32 + מסך + מגע | ✅ עובד |
| WiFi + MQTT + NTP config | ✅ |
| 4 טאבים + פעולות מגע | ✅ |
| שומר מסך NEON HUD (עיניים + כובע + כתר) | ✅ נצרב |
| `/esp_view`, `/esp_sync`, `/esp_msg`, `/esp_led` | ✅ |
| סוכן מקומי ברקע (VBS Startup) | ✅ |
| `/esp_flash`, `/esp_compile`, `/esp_ports`, `/esp_chipid`, `/agent_status` | ✅ |
| HANDOFF ראשוני | ✅ fc1ed8c |

### מה עוד פתוח

**🔴 שעון לא מסונכרן**
- ה-patch האחרון (`patch_ntp3.py`) **נכשל** עם `ANCHOR2_NOT_FOUND` — לא הוחל.
- הצריבה שאחריו צרבה את אותה קושחה ללא שינוי.
- **המשך טיפול:** לכתוב patch שלא תלוי בהתאמת רווחים מדויקת. למחוק כל שורת `configTime` ואז להוסיף מחדש מיד אחרי `connectWifi()` עם grep גמיש.

**🟡 מצמוץ שומר מסך לא חלק**
- הנצנוץ בין מצבי עיניים פקוחות/עצומות עדיין מורגש.
- **המשך טיפול:** להקטין את אזור ה-`fillRect` סביב העיניים או להעביר את כל ה-screensaver ל-sprite קטן.

**🟡 כפתורים איטיים (~1-2s תגובה)**
- 3 גורמים: debounce 400ms + MQTT round-trip + `drawEyes` לפני כל פעולה.
- **המשך טיפול:** debounce ל-150ms, ביטול ציור מלא לפני כל פעולה, אופציונלי: sprite לאזור הכפתור.

**🟡 `/esp_state` טרם נבנה**
- סנאפשוט מלא של ESP + סוכן + בוט בפקודה אחת.

**🔴 `/agent_submit` — BLOCKER נפרד**
- נמצא באודיט מקביל (לא קשור ל-ESP): משתמש רגיל יכול להנפיק +10 Credits דרך `/agent_submit` בלי approval/idempotency.
- **המשך טיפול:** לסגור את ה-blocker בנפרד לפני עליה לפרודקשן.

### לקחים מהסשן

1. **patch לא מחזיר `PATCHED` → לא מריצים `pio run -t upload`.** בזבוז של 30 שניות לכל צריבה מיותרת.
2. **לא להריץ קוד C++ ישירות ב-PowerShell.** PowerShell מריץ PowerShell, לא C++. שגיאות `CommandNotFoundException` הן סימן לכך.
3. **`configTime` לפני `connectWifi` נכשל בשקט** — הוא מנסה DNS בלי רשת. תמיד להעביר אותו אחרי.
4. **`serial.Serial` תופס COM9 לנצח** אם לא סוגרים — כל patch צריך `Get-Process python | Stop-Process -Force` לפני קריאה.
5. **`pio monitor` רץ ברקע תופס COM9 גם הוא** — לסגור לפני עריכה.

### זמני אמת (כיול)

| בלוק | הערכתי | בפועל |
|---|---|---|
| פקודה פשוטה (git push, patch) | 2-3 דק' | 3-4 דק' |
| פקודה + צריבה | 4-6 דק' | 6-8 דק' |
| patch גדול + צריבה | 8-10 דק' | 10-15 דק' |
| patch מורכב + צריבה + בדיקה | 15-20 דק' | 20-30 דק' |

**מכאן והלאה:** אם patch לא מחזיר `PATCHED` — לעצור, לא לצרוב.

