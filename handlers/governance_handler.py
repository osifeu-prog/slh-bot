import json
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[1]
GOV_PATH = BASE_DIR / "state" / "governance.json"
DB_PATH = BASE_DIR / "state" / "db.json"


def _load_gov():
    return json.loads(GOV_PATH.read_text(encoding="utf-8-sig"))


def _save_gov(gov):
    GOV_PATH.write_text(
        json.dumps(gov, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _load_db():
    return json.loads(DB_PATH.read_text(encoding="utf-8-sig"))


def _get_role(uid):
    db = _load_db()
    user = db.get("users", {}).get(str(uid), {})
    return user.get("role", "student").lower()


def _get_weight(gov, uid):
    role = _get_role(uid)
    return gov.get("rules", {}).get("vote_weights", {}).get(role, 1)


def register(bot, context=None):
    @bot.message_handler(commands=["agent_status"])
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

        gov = _load_gov()
        reg = gov.get("agents_registry", {})

        if aid not in reg:
            bot.reply_to(m, f"סוכן {aid} לא נמצא.")
            return

        uid = str(m.from_user.id)
        weight = _get_weight(gov, uid)

        gov.setdefault("individual_agent_votes", {})
        vote_key = f"agent_{aid}_{uid}"

        gov["individual_agent_votes"][vote_key] = {
            "agent_id": aid,
            "voter": uid,
            "action": action,
            "weight": weight,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        _save_gov(gov)

        bot.reply_to(
            m,
            f"הצבעה נרשמה:\n"
            f"סוכן {aid} → {action}\n"
            f"משקל: {weight}"
        )

    @bot.message_handler(commands=["gov_propose"])
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

        gov = _load_gov()
        proposals = gov.setdefault("proposals", [])

        proposal_id = len(proposals) + 1

        proposals.append({
            "id": proposal_id,
            "type": "proposal",
            "title": title,
            "description": desc,
            "status": "open",
            "created_by": str(m.from_user.id),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "votes": {
                "yes": 0,
                "no": 0,
                "abstain": 0,
                "weighted_yes": 0,
                "weighted_no": 0
            }
        })

        _save_gov(gov)

        bot.reply_to(
            m,
            f"הצעה #{proposal_id} נוצרה:\n"
            f"📌 {title}"
        )

    @bot.message_handler(commands=["gov_vote"])
    def gov_vote_cmd(m):
        parts = (m.text or "").split()

        if len(parts) < 3:
            bot.reply_to(m, "שימוש: /gov_vote <proposal_id> <yes|no|abstain>")
            return

        try:
            pid = int(parts[1])
        except ValueError:
            bot.reply_to(m, "proposal_id חייב להיות מספר.")
            return

        choice = parts[2].lower()

        if choice not in ("yes", "no", "abstain"):
            bot.reply_to(m, "הצבעה חייבת להיות yes / no / abstain.")
            return

        gov = _load_gov()
        proposals = gov.get("proposals", [])

        if pid < 1 or pid > len(proposals):
            bot.reply_to(m, "הצעה לא קיימת.")
            return

        proposal = proposals[pid - 1]

        if proposal.get("status") != "open":
            bot.reply_to(m, "ההצעה כבר סגורה.")
            return

        uid = str(m.from_user.id)
        weight = _get_weight(gov, uid)

        individual_votes = gov.setdefault("individual_votes", {})
        vote_key = f"p{pid}_{uid}"

        if vote_key in individual_votes:
            bot.reply_to(m, "כבר הצבעת על הצעה זו.")
            return

        individual_votes[vote_key] = {
            "proposal_id": pid,
            "voter": uid,
            "choice": choice,
            "weight": weight,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        votes = proposal["votes"]

        if choice == "yes":
            votes["yes"] = votes.get("yes", 0) + 1
            votes["weighted_yes"] = votes.get("weighted_yes", 0) + weight
        elif choice == "no":
            votes["no"] = votes.get("no", 0) + 1
            votes["weighted_no"] = votes.get("weighted_no", 0) + weight
        else:
            votes["abstain"] = votes.get("abstain", 0) + 1

        _save_gov(gov)

        bot.reply_to(
            m,
            f"הצבעה נרשמה:\n"
            f"הצעה #{pid} → {choice}\n"
            f"משקל: {weight}"
        )

    @bot.message_handler(commands=["gov_tally"])
    def gov_tally_cmd(m):
        parts = (m.text or "").split()

        if len(parts) < 2:
            bot.reply_to(m, "שימוש: /gov_tally <proposal_id>")
            return

        try:
            pid = int(parts[1])
        except ValueError:
            bot.reply_to(m, "proposal_id חייב להיות מספר.")
            return

        gov = _load_gov()
        proposals = gov.get("proposals", [])

        if pid < 1 or pid > len(proposals):
            bot.reply_to(m, "הצעה לא קיימת.")
            return

        proposal = proposals[pid - 1]
        votes = proposal.get("votes", {})

        weighted_yes = votes.get("weighted_yes", 0)
        weighted_no = votes.get("weighted_no", 0)
        total_weight = weighted_yes + weighted_no

        if total_weight == 0:
            bot.reply_to(m, "אין הצבעות.")
            return

        threshold = gov.get("rules", {}).get("pass_threshold", 0.6)
        ratio = weighted_yes / total_weight

        if ratio >= threshold:
            proposal["status"] = "approved"
            _save_gov(gov)

            # Bridge: create a developer mission automatically
            try:
                from core.mission_lifecycle import MissionLifecycleService
                service = MissionLifecycleService()
                mission_id = f"gov_{proposal['id']}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
                mission_description = proposal.get("title") or proposal.get("description") or f"Proposal {proposal['id']}"
                mission_result = service.create_mission(
                    mission_id,
                    mission_description,
                    reward=0
                )
                mission_status = mission_result.get("status") or "unknown"
                mission_msg = f"\n🎯 משימה נוצרה: {mission_id} [{mission_status}]"
            except Exception as e:
                mission_msg = f"\n⚠️ לא ניתן ליצור משימה: {e}"

            bot.reply_to(
                m,
                f"✅ הצעה #{pid} אושרה\n"
                f"כן: {weighted_yes}\n"
                f"לא: {weighted_no}\n"
                f"יחס: {ratio:.2f}"
                + mission_msg
            )
        else:
            proposal["status"] = "rejected"
            _save_gov(gov)
            bot.reply_to(
                m,
                f"❌ הצעה #{pid} נדחתה\n"
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

        gov = _load_gov()

        if agent_id not in gov.get("agents_registry", {}):
            bot.reply_to(m, f"סוכן {agent_id} לא נמצא.")
            return

        session_id = len(gov.get("sessions", [])) + 1

        gov.setdefault("sessions", []).append({
            "id": session_id,
            "agent_id": agent_id,
            "summary": summary,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        _save_gov(gov)

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

        outcome = parts[2].strip()

        gov = _load_gov()
        sessions = gov.get("sessions", [])

        if session_id < 1 or session_id > len(sessions):
            bot.reply_to(m, "Session לא קיים.")
            return

        session = sessions[session_id - 1]
        session["status"] = "closed"
        session["outcome"] = outcome
        session["closed_at"] = datetime.now(timezone.utc).isoformat()

        _save_gov(gov)

        bot.reply_to(
            m,
            f"Session #{session_id} נסגר.\n"
            f"תוצאה: {outcome}"
        )
