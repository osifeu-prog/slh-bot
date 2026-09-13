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