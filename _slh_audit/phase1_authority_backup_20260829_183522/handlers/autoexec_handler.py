from core.authority import is_owner
from core.exec_policy import run_gated


def register(bot, context=None):

    @bot.message_handler(commands=["autoexec"])
    def autoexec_cmd(m):

        if not is_owner(m):
            bot.reply_to(m, "⛔ Owner only.")
            return

        lines = (m.text or "").split("\n")
        output = []
        i = 1

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            if line.startswith("/exec_batch"):
                batch = []
                i += 1

                while i < len(lines) and lines[i].strip() != "/endbatch":
                    batch.append(lines[i])
                    i += 1

                if i >= len(lines):
                    output.append("❌ Missing /endbatch")
                    break

                cmd = "\n".join(batch)

                ok, result = run_gated(
                    m.from_user.id,
                    cmd,
                    source="telegram:autoexec:batch",
                    timeout=30,
                )

                if not ok:
                    output.append(f"❌ BATCH BLOCKED/FAILED\n{result}")
                    break

                output.append(f"✅ BATCH\n{result}")

            elif line.startswith("/exec "):
                cmd = line[6:]

                ok, result = run_gated(
                    m.from_user.id,
                    cmd,
                    source="telegram:autoexec",
                    timeout=15,
                )

                if not ok:
                    output.append(f"❌ {cmd}\n{result}")
                    break

                output.append(f"✅ {cmd}\n{result}")

            i += 1

        bot.reply_to(
            m,
            "\n\n".join(output)[:4000]
            if output
            else "ℹ️ No commands found.",
        )
