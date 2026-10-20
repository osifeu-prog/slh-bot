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

        # One canonical snapshot only: academy_manager.progress() delegates to
        # get_user(), which can create a profile for a missing UID.
        db_snapshot = profile_manager.load_db()
        users = db_snapshot.get("users", {}) if isinstance(db_snapshot, dict) else {}
        user = users.get(uid, {}) if isinstance(users, dict) else {}
        user = user if isinstance(user, dict) else {}
        academy = user.get("academy", {})
        academy = academy if isinstance(academy, dict) else {}
        saved_courses = academy.get("courses", {})
        saved_courses = saved_courses if isinstance(saved_courses, dict) else {}
        active_course = academy.get("active_course")
        data = {}
        for course_id, state in saved_courses.items():
            if not isinstance(state, dict):
                continue
            data[str(course_id)] = {
                "stage": state.get("stage", 0),
                "completed": state.get("completed", []),
                "active": str(course_id) == str(active_course),
            }

        gamification = user.get("gamification", {})
        gamification = gamification if isinstance(gamification, dict) else {}
        points = gamification.get("points")
        level = gamification.get("level")

        lines = ["🎓 דוח ההתקדמות הלימודית שלך", ""]
        if points is not None or level is not None:
            game_parts = []
            if points is not None:
                game_parts.append(f"נקודות מערכת: {points}")
            if level is not None:
                game_parts.append(f"רמה: {level}")
            lines.append("⭐ " + " · ".join(game_parts))
            lines.append("")

        catalog = (academy_manager.get_courses() or {}) if data else {}
        total_completed = 0
        total_stages = 0
        course_rows = []
        for course_id, state in data.items():
            course = catalog.get(course_id) if isinstance(catalog, dict) else None
            course = course if isinstance(course, dict) else {}
            title = str(course.get("title") or course_id)
            stage_defs = course.get("stages", [])
            valid_ids = set()
            if isinstance(stage_defs, list):
                for stage_def in stage_defs:
                    if not isinstance(stage_def, dict):
                        continue
                    try:
                        valid_ids.add(int(stage_def.get("id")))
                    except (TypeError, ValueError, OverflowError):
                        continue

            raw_completed = state.get("completed", [])
            completed_ids = set()
            if isinstance(raw_completed, (list, tuple, set)):
                for value in raw_completed:
                    try:
                        completed_ids.add(int(value))
                    except (TypeError, ValueError, OverflowError):
                        continue
            completed_count = len(completed_ids & valid_ids) if valid_ids else len(completed_ids)
            total_count = len(valid_ids)
            total_completed += completed_count
            total_stages += total_count
            if total_count:
                pct = round(100 * completed_count / total_count)
                progress_text = f"{completed_count}/{total_count} שיעורים ({pct}%)"
                if completed_count == total_count:
                    status = "הושלם"
                elif state.get("active"):
                    status = "פעיל"
                else:
                    status = "בתהליך"
            else:
                progress_text = f"{completed_count} שיעורים שהושלמו · קטלוג לא זמין"
                status = "לא מאומת"

            course_rows.append(
                f"📘 {title}\n"
                f"   {progress_text} · {status}"
            )

        if course_rows:
            lines.extend(course_rows)
            lines.append("")
            if total_stages:
                overall_pct = round(100 * total_completed / total_stages)
                lines.append(
                    f"📊 סה״כ בקורסים שלך: {total_completed}/{total_stages} "
                    f"שיעורים ({overall_pct}%)"
                )
        else:
            lines.extend([
                "עדיין אין קורסים עם התקדמות שמורה.",
                "התחל דרך /courses",
            ])

        lines.extend([
            "",
            "הדוח מבוסס על user.academy.courses ועל קטלוג הקורסים.",
            "נקודות המערכת מוצגות בנפרד; אין כאן שדה נפרד בשם hebrew_score.",
        ])
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
