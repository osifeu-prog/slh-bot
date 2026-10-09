import json
from pathlib import Path
from datetime import datetime, timezone

from core import governance_store

BASE_DIR = Path(__file__).resolve().parents[1]
GOV_PATH = BASE_DIR / "state" / "governance.json"
DB_PATH = BASE_DIR / "state" / "db.json"


def _load_gov():
    """Read canonical Governance state with legacy fallback inside the store."""
    return governance_store.load_governance()


def _save_gov(gov):
    """Compatibility wrapper: persist Governance to the canonical database."""
    return governance_store.save_governance(gov)


def _load_db():
    return json.loads(DB_PATH.read_text(encoding="utf-8-sig"))


def _get_role(uid):
    db = _load_db()
    user = db.get("users", {}).get(str(uid), {})
    return user.get("role", "student").lower()


def _get_weight(gov, uid):
    role = _get_role(uid)
    return gov.get("rules", {}).get("vote_weights", {}).get(role, 1)


def _parse_proposal_id(value):
    """Accept proposal IDs as plain numbers or Telegram-style #123."""
    raw = str(value).strip()
    if raw.startswith("#"):
        raw = raw[1:].strip()
    if not raw.isdigit():
        raise ValueError("PROPOSAL_ID_INVALID")
    proposal_id = int(raw)
    if proposal_id < 1:
        raise ValueError("PROPOSAL_ID_INVALID")
    return proposal_id


def register(bot, context=None):
    @bot.message_handler(commands=["gov_agent_status"])
    def agent_status_cmd(m):
        gov = _load_gov()
        reg = gov.get("agents_registry", {})

        if not reg:
            bot.reply_to(m, "אין סוכנים רשומים.")
            return

        lines = []
        for aid, a in reg.items():
            lines.append(
                f"{aid} — {a.get('name', 'unknown')} "
                f"[{a.get('status', 'unknown')}]"
            )

        bot.reply_to(m, "🤖 סוכנים רשומים:\n" + "\n".join(lines))

    @bot.message_handler(commands=["agent_vote"])
    def agent_vote_cmd(m):
        parts = (m.text or "").split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(m, "שימוש: /agent_vote <id> <approve|pause|revoke>")
            return
        aid = parts[1].strip()
        action = parts[2].strip().lower()
        if action not in ("approve", "pause", "revoke"):
            bot.reply_to(m, "פעולה חייבת להיות approve / pause / revoke.")
            return
        uid = str(m.from_user.id)
        role = _get_role(uid)
        try:
            def mutate(gov):
                reg = gov.get("agents_registry", {})
                if aid not in reg:
                    raise ValueError("AGENT_NOT_FOUND")
                weight = int(gov.get("rules", {}).get("vote_weights", {}).get(role, 1) or 1)
                votes = gov.setdefault("individual_agent_votes", {})
                votes[f"agent_{aid}_{uid}"] = {
                    "agent_id": aid,
                    "voter": uid,
                    "action": action,
                    "weight": weight,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                return weight
            weight = governance_store.update_governance(mutate)
        except ValueError as exc:
            bot.reply_to(m, "סוכן לא נמצא." if str(exc) == "AGENT_NOT_FOUND" else f"שגיאה: {exc}")
            return
        bot.reply_to(
            m,
            f"הצבעה נרשמה:\n"
            f"סוכן {aid} → {action}\n"
            f"משקל: {weight}"
        )

    @bot.message_handler(commands=["propose", "gov_propose"])
    def gov_propose_cmd(m):
        body = (m.text or "").split(maxsplit=1)
        if len(body) < 2:
            bot.reply_to(m, "שימוש: /gov_propose <title> | <description>")
            return
        raw = body[1]
        if "|" in raw:
            title, desc = raw.split("|", 1)
        else:
            title, desc = raw, ""
        title = title.strip()
        desc = desc.strip()
        try:
            proposal = governance_store.create_proposal(
                title=title,
                description=desc,
                created_by=str(m.from_user.id),
            )
        except ValueError as exc:
            messages = {
                "PROPOSAL_TITLE_REQUIRED": "צריך להזין כותרת להצעה.",
                "PROPOSAL_CREATOR_REQUIRED": "לא ניתן לזהות את יוצר ההצעה.",
                "PROPOSALS_INVALID": "מבנה ההצעות אינו תקין.",
            }
            bot.reply_to(m, messages.get(str(exc), f"שגיאה ביצירת הצעה: {exc}"))
            return
        bot.reply_to(
            m,
            f"הצעה #{proposal['id']} נוצרה במקור האמת הקנוני:\n"
            f"📌 {proposal['title']}"
        )

    @bot.message_handler(commands=["vote", "gov_vote"])
    def gov_vote_cmd(m):
        parts = (m.text or "").split()
        if len(parts) < 3:
            bot.reply_to(m, "שימוש: /vote <proposal_id> <yes|no|abstain>")
            return

        try:
            pid = _parse_proposal_id(parts[1])
        except ValueError:
            bot.reply_to(m, "proposal_id חייב להיות מספר.")
            return

        choice = parts[2].lower()
        if choice not in ("yes", "no", "abstain"):
            bot.reply_to(m, "הצבעה חייבת להיות yes / no / abstain.")
            return

        try:
            from core.tokenomics import rewards_snapshot
            result = governance_store.record_vote(
                proposal_id=pid,
                voter_uid=str(m.from_user.id),
                choice=choice,
                reward_points=rewards_snapshot().get("vote_points", 0),
            )
        except ValueError as exc:
            errors = {
                "PROPOSAL_ID_INVALID": "proposal_id חייב להיות מספר.",
                "VOTE_CHOICE_INVALID": "הצבעה חייבת להיות yes / no / abstain.",
                "PROPOSAL_NOT_FOUND": "הצעה לא קיימת.",
                "PROPOSAL_CLOSED": "ההצעה כבר סגורה.",
            }
            bot.reply_to(m, errors.get(str(exc), f"שגיאה בהצבעה: {exc}"))
            return

        if result["status"] == "already_voted":
            bot.reply_to(m, f"כבר הצבעת על הצעה #{pid}.")
            return

        slh = result.get("slh_context", {})
        bot.reply_to(
            m,
            f"✅ הצבעה נרשמה:\n"
            f"הצעה #{pid} → {choice}\n"
            f"משקל: {result['weight']}\n"
            f"+{result['points_awarded']} Points ← Leaderboard\n"
            f"SLH snapshot: {slh.get('token_balance', 0)}"
        )

    @bot.message_handler(commands=["tally", "gov_tally"])
    def gov_tally_cmd(m):
        parts = (m.text or "").split()
        if len(parts) < 2:
            bot.reply_to(m, "שימוש: /gov_tally <proposal_id>")
            return
        try:
            pid = _parse_proposal_id(parts[1])
        except ValueError:
            bot.reply_to(m, "proposal_id חייב להיות מספר.")
            return
        try:
            result = governance_store.finalize_proposal(proposal_id=pid)
        except ValueError as exc:
            messages = {
                "PROPOSAL_ID_INVALID": "proposal_id חייב להיות מספר.",
                "PROPOSAL_NOT_FOUND": "הצעה לא קיימת.",
                "PROPOSAL_CLOSED": "ההצעה כבר נסגרה.",
                "NO_VOTES": "אין הצבעות.",
                "PROPOSALS_INVALID": "מבנה ההצעות אינו תקין.",
                "VOTE_TALLY_INVALID": "נתוני ספירת ההצבעות אינם תקינים.",
            }
            bot.reply_to(m, messages.get(str(exc), f"שגיאה בספירת הצבעות: {exc}"))
            return
        weighted_yes = result["weighted_yes"]
        weighted_no = result["weighted_no"]
        ratio = result["ratio"]
        if result["status"] == "approved":
            mission_msg = ""
            try:
                from core.mission_lifecycle import MissionLifecycleService
                service = MissionLifecycleService()
                mission_id = f"gov_{pid}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
                mission_description = result.get("title") or result.get("description") or f"Proposal {pid}"
                mission_result = service.create_mission(mission_id, mission_description, reward=0)
                mission_status = mission_result.get("status") or "unknown"
                mission_msg = f"\n🎯 משימה נוצרה: {mission_id} [{mission_status}]"
            except Exception:
                mission_msg = "\n⚠️ ההצעה אושרה, אבל יצירת המשימה לא אומתה."
            bot.reply_to(
                m,
                f"✅ הצעה #{pid} אושרה במקור האמת הקנוני\n"
                f"כן: {weighted_yes}\n"
                f"לא: {weighted_no}\n"
                f"יחס: {ratio:.2f}"
                + mission_msg
            )
        else:
            bot.reply_to(
                m,
                f"❌ הצעה #{pid} נדחתה במקור האמת הקנוני\n"
                f"כן: {weighted_yes}\n"
                f"לא: {weighted_no}\n"
                f"יחס: {ratio:.2f}"
            )

    @bot.message_handler(commands=["gov_status"])
    def gov_status_cmd(m):
        gov = _load_gov()
        agents = gov.get("agents_registry", {})
        proposals = gov.get("proposals", [])

        open_proposals = [p for p in proposals if p.get("status") == "open"]

        bot.reply_to(
            m,
            "🗳️ SLH Governance\n\n"
            f"🤖 סוכנים: {len(agents)}\n"
            f"📌 הצעות: {len(proposals)}\n"
            f"🟢 פתוחות: {len(open_proposals)}\n"
            f"🏛️ מקור אמת: {gov.get('source_of_truth')}"
        )

    @bot.message_handler(commands=["session_new"])
    def session_new_cmd(m):
        parts = (m.text or "").split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(m, "שימוש: /session_new <agent_id> <summary>")
            return
        agent_id = parts[1].strip()
        summary = parts[2].strip()
        try:
            def mutate(gov):
                if agent_id not in gov.get("agents_registry", {}):
                    raise ValueError("AGENT_NOT_FOUND")
                sessions = gov.setdefault("sessions", [])
                session_ids = []
                for item in sessions:
                    if isinstance(item, dict):
                        try:
                            session_ids.append(int(item.get("id", 0)))
                        except (TypeError, ValueError):
                            pass
                session_id = max(session_ids, default=0) + 1
                sessions.append({
                    "id": session_id,
                    "agent_id": agent_id,
                    "summary": summary,
                    "status": "active",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                return session_id
            session_id = governance_store.update_governance(mutate)
        except ValueError as exc:
            bot.reply_to(m, "סוכן לא נמצא." if str(exc) == "AGENT_NOT_FOUND" else f"שגיאה: {exc}")
            return
        bot.reply_to(
            m,
            f"Session #{session_id} נפתח עבור סוכן {agent_id}.\n"
            f"📝 {summary}"
        )

    @bot.message_handler(commands=["session_close"])
    def session_close_cmd(m):
        parts = (m.text or "").split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(m, "שימוש: /session_close <session_id> <outcome>")
            return
        try:
            session_id = int(parts[1])
        except ValueError:
            bot.reply_to(m, "session_id חייב להיות מספר.")
            return
        if session_id < 1:
            bot.reply_to(m, "session_id חייב להיות מספר חיובי.")
            return
        outcome = parts[2].strip()
        try:
            def mutate(gov):
                sessions = gov.get("sessions", [])
                if not isinstance(sessions, list):
                    raise ValueError("SESSIONS_INVALID")
                session = None
                for item in sessions:
                    if not isinstance(item, dict):
                        continue
                    try:
                        item_id = int(item.get("id", 0))
                    except (TypeError, ValueError):
                        continue
                    if item_id == session_id:
                        session = item
                        break
                if session is None:
                    raise ValueError("SESSION_NOT_FOUND")
                if session.get("status") == "closed":
                    raise ValueError("SESSION_CLOSED")
                session["status"] = "closed"
                session["outcome"] = outcome
                session["closed_at"] = datetime.now(timezone.utc).isoformat()
                return dict(session)
            governance_store.update_governance(mutate)
        except ValueError as exc:
            messages = {
                "SESSIONS_INVALID": "מבנה הסשנים אינו תקין.",
                "SESSION_NOT_FOUND": "Session לא קיים.",
                "SESSION_CLOSED": "Session כבר סגור.",
            }
            bot.reply_to(m, messages.get(str(exc), f"שגיאה: {exc}"))
            return
        bot.reply_to(
            m,
            f"Session #{session_id} נסגר במקור האמת הקנוני.\n"
            f"תוצאה: {outcome}"
        )
