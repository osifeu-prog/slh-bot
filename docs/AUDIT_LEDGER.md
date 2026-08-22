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
