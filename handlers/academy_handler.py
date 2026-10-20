from core import academy_manager
from core import lesson_engine
from core import profile_manager


def _stars_price(store_item):
    try:
        import json
        with open("store/items.json", encoding="utf-8") as f:
            return (json.load(f).get(store_item) or {}).get("price_stars")
    except Exception:
        return None


def _access_label(data):
    if data.get("access") != "paid":
        return "חינם"
    price = _stars_price(data.get("store_item", ""))
    return f"{price}⭐" if price else "בתשלום"


def _paid_course_lock(uid, course_id):
    """Return a purchase message when the central course authority denies access."""
    course = academy_manager.get_courses().get(course_id) or {}
    if course.get("access") != "paid":
        return None
    if lesson_engine.has_course_access(uid, course_id):
        return None
    item = course.get("store_item", "")
    price = _stars_price(item)
    return (
        f"🔒 {course.get('title', course_id)} הוא קורס בתשלום"
        + (f" ({price}⭐)" if price else "")
        + f".\n\nלרכישה: /buystars {item}"
    )


def register(bot):

    @bot.message_handler(commands=['courses'])
    def courses(m):
        # Keep /courses and /academy on the same canonical interactive UI.
        # This gives completed courses a real reopen path instead of a dead-end text list.
        from handlers.academy_menu_handler import _send_academy
        _send_academy(
            bot,
            m.chat.id,
            str(m.from_user.id),
        )

    @bot.message_handler(commands=['academy_progress'])
    def progress(m):
        uid = str(m.from_user.id)
        data = academy_manager.progress(uid)

        if not data:
            bot.reply_to(
                m,
                "📊 עדיין אין התקדמות לימודית שמורה.\n\n"
                "התחל או פתח קורס דרך /courses"
            )
            return

        catalog = academy_manager.get_courses() or {}
        user = profile_manager.get_user(uid) or {}
        stored_courses = (
            user.get("academy", {}).get("courses", {})
            if isinstance(user, dict) else {}
        )
        total_done = 0
        total_stages = 0
        lines = ["📚 ההתקדמות הלימודית שלך", ""]

        for course_id, state in data.items():
            course = catalog.get(course_id, {}) if isinstance(catalog, dict) else {}
            if not isinstance(course, dict):
                course = {}
            title = course.get("title") or course.get("name") or course_id

            stage_ids = set()
            for stage_item in course.get("stages", []):
                if not isinstance(stage_item, dict):
                    continue
                try:
                    stage_ids.add(int(stage_item.get("id")))
                except (TypeError, ValueError):
                    continue

            completed_ids = set()
            for completed_stage in state.get("completed", []) or []:
                try:
                    completed_ids.add(int(completed_stage))
                except (TypeError, ValueError):
                    continue

            if stage_ids:
                completed_count = len(stage_ids & completed_ids)
                stage_count = len(stage_ids)
                percent = round(completed_count * 100 / stage_count)
                total_done += completed_count
                total_stages += stage_count
                progress_label = f"{completed_count}/{stage_count} שיעורים ({percent}%)"
            else:
                progress_label = f"{len(completed_ids)} שיעורים שהושלמו"

            status = "פעיל" if state.get("active") else "לא פעיל"
            lines.append(
                f"📘 {title}: {progress_label} | שלב שמור: {state.get('stage', 0)} | {status}"
            )

            stored = stored_courses.get(course_id, {}) if isinstance(stored_courses, dict) else {}
            if isinstance(stored, dict) and stored.get("certification_passed_at"):
                lines.append("   🎓 הסמכה: עברה")

        if total_stages:
            overall = round(total_done * 100 / total_stages)
            lines[1:1] = [
                f"סה״כ בקורסים הרשומים: {total_done}/{total_stages} שיעורים ({overall}%)",
                "",
            ]

        bot.reply_to(m, "\n".join(lines))
    @bot.message_handler(func=lambda m: m.text and m.text.startswith("/course_"))
    def start_course(m):
        uid = str(m.from_user.id)
        course_id = m.text.replace("/course_", "", 1).split()[0]
        locked = _paid_course_lock(uid, course_id)
        if locked:
            bot.reply_to(m, locked)
            return
        ok = academy_manager.start_course(uid, course_id)

        if ok:
            bot.reply_to(
                m,
                f"✅ התחלת קורס:\n{course_id}\n\n"
                f"להתחיל את השיעור הראשון:\n/lesson {course_id} 1\n\n"
                "בסיום כל שיעור: 25 נקודות"
            )
        else:
            bot.reply_to(m, "❌ קורס לא נמצא")

    @bot.message_handler(commands=['complete'])
    def complete(m):
        parts = m.text.split()
        uid = str(m.from_user.id)

        # Compatibility command: /complete <stage> uses the active course,
        # but still passes through the same lesson authority as /finish.
        if len(parts) == 2:
            user = profile_manager.get_user(uid)
            course_id = user.get("academy", {}).get("active_course")
            stage_raw = parts[1]
        elif len(parts) == 3:
            course_id = parts[1]
            stage_raw = parts[2]
        else:
            bot.reply_to(
                m,
                "שימוש:\n/complete <stage>\n"
                "או\n/complete <course_id> <stage>"
            )
            return

        try:
            stage = int(stage_raw)
        except (TypeError, ValueError):
            bot.reply_to(m, "מספר שלב לא תקין")
            return

        if not course_id:
            bot.reply_to(m, "❌ אין קורס פעיל. התחל דרך /courses")
            return

        result = lesson_engine.complete_lesson(
            uid,
            course_id,
            stage
        )

        if result.get("already_completed"):
            bot.reply_to(m, "ℹ️ כבר השלמת את השיעור הזה")
            return

        if not result.get("ok"):
            error = result.get("error")
            if error == "course_locked":
                message = _paid_course_lock(uid, course_id) or "🔒 אין לך הרשאה לקורס הזה."
            elif error == "sequential_access":
                message = "🔒 השלב נעול. יש להשלים קודם את השלב הקודם."
            elif error == "course_not_started":
                message = "❌ הקורס עדיין לא התחיל. התחל דרך /courses"
            elif error == "course_not_found":
                message = "❌ קורס לא נמצא"
            elif error == "trader_certification_required":
                message = "🔒 יש לעבור תחילה את מבחן הסמכת הסוחר: /trader_test"
            else:
                message = "❌ לא ניתן להשלים את השלב הזה"
            bot.reply_to(m, message)
            return

        reward = result.get("reward", {})
        bot.reply_to(
            m,
            "🎉 שלב הושלם!\n\n"
            f"⭐ נקודות: {reward.get('points', 0)}\n"
            f"💰 קרדיטים: {reward.get('credits', 0)}"
        )
