from core.exec_policy import is_admin, run_audit, run_gated
from core.authority import is_owner


def register(bot):
    @bot.message_handler(commands=["e"])
    def e_cmd(msg):
        uid = msg.from_user.id
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /e <command>")
            return

        cmd = parts[1].strip()
        if cmd.startswith("railway"):
            if not is_owner(uid):
                bot.reply_to(msg, "⛔️ OWNER only for Railway control-plane actions")
                return
            try:
                from core.railway_control import canonical_up, project, projects
                args = cmd.split()
                if args == ["railway"] or args == ["railway", "status"]:
                    ps = projects()
                    bot.reply_to(msg, f"🚂 Railway Control Plane\\nConnected projects: {len(ps)}\\n" + "\\n".join(f"• {p['name']} — {p['id']}" for p in ps[:30]))
                    return
                if args == ["railway", "projects"]:
                    ps = projects()
                    bot.reply_to(msg, "🚂 Railway PROJECTS\\n" + "\\n".join(f"• {p['name']} — {p['id']}" for p in ps[:50]))
                    return
                if args == ["railway", "up"]:
                    result = canonical_up()
                    bot.reply_to(
                        msg,
                        "🚀 RAILWAY DEPLOY TRIGGERED\\n"
                        f"Project: {result['project']}\\n"
                        f"Service: {result['service']}\\n"
                        f"Environment: {result['environment']}\\n"
                        f"Commit: {result['commit'][:12]}\\n"
                        f"Deployment: {result['deployment_id']}",
                    )
                    return
                if len(args) == 3 and args[1] == "inspect":
                    project_id = args[2].strip()
                    p = project(project_id)
                    if not p:
                        # Fall back to the same workspace listing used by
                        # `railway projects`, avoiding false "not found"
                        # when detailed project resolution is restricted.
                        ps = projects()
                        p = next(
                            (
                                item for item in ps
                                if str(item.get("id", "")).strip().lower()
                                == project_id.lower()
                            ),
                            None,
                        )
                    if not p:
                        bot.reply_to(msg, "❌ Railway project not found")
                        return
                    envs = p.get("environments", {}).get("edges", [])
                    svcs = p.get("services", {}).get("edges", [])
                    lines = [f"🚂 {p['name']} ({p['id']})"]
                    if envs or svcs:
                        lines.append("Environments:")
                        lines += [f"• {x['node']['name']} — {x['node']['id']}" for x in envs]
                        lines.append("Services:")
                        lines += [f"• {x['node']['name']} — {x['node']['id']}" for x in svcs]
                    else:
                        lines.append("⚠️ Project is visible in the workspace, but detailed environment/service metadata is not exposed to this runtime token.")
                    bot.reply_to(msg, "\\n".join(lines)[:4000])
                    return
                bot.reply_to(msg, "Usage: /e railway | railway projects | railway inspect <project_id> | railway up")
            except Exception as exc:
                bot.reply_to(msg, f"❌ Railway control: {exc}")
            return


            if not is_owner(uid):
                bot.reply_to(msg, "⛔️ OWNER only for Railway control-plane actions")
                return
            try:
                from core.railway_control import canonical_up
                result = canonical_up()
                bot.reply_to(
                    msg,
                    "🚀 RAILWAY DEPLOY TRIGGERED\\n"
                    f"Project: {result['project']}\\n"
                    f"Service: {result['service']}\\n"
                    f"Environment: {result['environment']}\\n"
                    f"Commit: {result['commit'][:12]}\\n"
                    f"Deployment: {result['deployment_id']}",
                )
            except Exception as exc:
                bot.reply_to(msg, f"❌ Railway control: {exc}")
            return

        if cmd in ("alpha_status", "alpha_open", "alpha_state"):
            if not is_owner(uid):
                bot.reply_to(msg, "⛔️ OWNER only for alpha control-plane actions")
                return
            try:
                from core.alpha_control_plane import (
                    alpha_state,
                    evaluate,
                    format_report,
                    open_alpha,
                )

                if cmd == "alpha_status":
                    bot.reply_to(msg, format_report(evaluate()))
                    return
                if cmd == "alpha_state":
                    bot.reply_to(msg, "ALPHA STATE\n" + str(alpha_state()))
                    return

                state = open_alpha(uid)
                bot.reply_to(msg, "🚀 ALPHA OPEN\n" + str(state))
                return
            except Exception as exc:
                bot.reply_to(msg, str(exc))
                return

        if is_owner(uid):
            ok, out = run_gated(uid, cmd, source="e", timeout=15)
        elif is_admin(uid):
            ok, out = run_audit(uid, cmd, source="e_admin_audit", timeout=15)
        else:
            bot.reply_to(msg, "⛔️ Admin/Developer access required")
            return

        bot.reply_to(msg, out[:4000] or "(no output)")
