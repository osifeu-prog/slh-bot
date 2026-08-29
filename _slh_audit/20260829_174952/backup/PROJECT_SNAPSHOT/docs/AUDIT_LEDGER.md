# SLH OS — Audit Ledger

> נוצר: 2026-08-22
> מטרה: מקור אמת לתהליך האודיט, המיון והשדרוג של SLH OS.
> עדכון: כל סבב אודיט מוסיף רשומה חדשה (אין למחוק היסטוריה).

---

## סטטוס נוכחי (22/08/2026)

### Entrypoint פעיל
- `bot_gateway.py` (נקבע ב־Procfile ו־railway.json)
- Flask + Telebot משולבים באותו תהליך

### Command Registry
- נמצאו כפילויות רבות: `start_course` x6, `next` x6, `course` x6, `activate` x6, `ton_*` x5, `ask` x4, `join` x3, `complete` x3, `status` x2, `diagnose` x2, `courses` x2, `progress` x2, `help` x2.
- רשימת הפקודות המוצגת ב־/help וב־/admin אינה משקפת את כל מה שרשום בקוד.

### Agents
- קיימים 9 רשומות ב־state/db.json → agents:
  - System: SystemGuard(1), DoctorAgent(2), SyncAgent(3), TokenAgent(4)
  - Personal: GuyTamagotchi(5), Osif-Agent(6), User6332323773-Agent(7), User8847192372-Agent(8), גיא גולדשטיין-Agent(9)
- חסר שדה `agent_type` מפורש (`system` / `personal` / `device`)
- חסרה הפרדת הרשאות לפי שכבה

### Devices
- קיים `state/devices.json` ו־device_handler.py
- אין קישור `agent_id` <-> `device_id` באף צד
- `device_bridge.py` כרגע in-memory בלבד, ללא MQTT/WebSocket אמיתי

### Onboarding
- `join_handler.py` קיים ומבצע רישום רב-שלבי (name, group) ויוצר profile
- **לא אותר start_handler נפרד** — דרוש מיקוד

---

## החלטות שהתקבלו
1. לבנות **Agent Taxonomy** ברורה: system / personal / device.
2. לאחד את כל ה־handlers תחת **Router אחיד** במקום ריבוי entrypoints.
3. לתעד כל צעד ב־AUDIT_LEDGER.md (הקובץ הזה).
4. להפריד בין Agents, Tasks, Devices, Journal ברמת state.

## Next Steps (סבב 2)
- [ ] לאתר את ה־start handler המדויק (חיפוש ממוקד)
- [ ] למפות את כל הפקודות מול התפריטים
- [ ] להגדיר schema מוצע ל־Agent Taxonomy
- [ ] לבדוק האם יש צורך ב־backfill של שדה `agent_type` לסוכנים קיימים

## Checkpoint — 2026-08-22 17:49 UTC — ALPHA_CORE_SMOKE_PASS

Full 16-command smoke test: 16/16 PASS.
- Runtime: bot_gateway.py stable, PID 1
- Economy authority: verified locked (bridge → economy_service)
- LLM intent routing: fixed — "status" alone → LLM, "מה מצב המערכת" → canonical report (intended)
- Identity: OWNER consistent across /me, /wallet, /ask
- Agents: 9 registered, 1/9 with real runtime_class (SystemGuard)
- Devices: 5 registered, all offline, no agent↔️device link
- Binance/BSC/BNB: confirmed absent — no code, no env vars. Not a bug.

Open for next session:
- Agent taxonomy (system/personal/user scope) — design only, no code yet
- core/authority.py Gate — not created
- Windows local repo (C:\Users\USER\slh-bot-clean) still far behind origin/main — needs separate backup+sync session
- learning_path.py / plugins/task.py mojibake — not fixed
- Legacy save_db() duplicates (bot_stable.py etc.) — dead code, low priority

Tag: ALPHA_CORE_SMOKE_PASS_20260822

## Checkpoint 2026-08-22T14:59:16.120368+00:00

### Verified
- Runtime: bot_gateway.py (PID 1)
- Procfile: web: /opt/venv/bin/python3 -B bot_gateway.py
- /start handler: handlers/onboarding_v2.py:116
- Loader: handlers.loader
- Economy authority: core/economy_bridge.py -> economy_service.record_transaction()
- Identity: OWNER_ID=8789977826; no get_role/get_permissions in core.identity yet
- Agents: 9 in state/db.json; no agent_type/visibility fields
- Devices: state/devices.json, all offline; no agent_id link
- Crypto: TON wallet/handler exist; Binance/BSC/BNB/Web3 absent
- LLM router: /ask status no longer triggers system report
- Health: /health returns ok
- Smoke: all 16 commands passed

### Decision
- Freeze Alpha Core; no new feature work tonight.
- Next priorities:
  1. Agent Scope/Visibility
  2. Authority Gate
  3. optional Binance module

### Notes
- bot_stable.py is legacy, not production entrypoint.
- Several audit scripts are read-only or legacy; no production impact.
