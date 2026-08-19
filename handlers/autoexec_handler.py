import subprocess
from security.permissions import has_permission


def register(bot, context=None):

    @bot.message_handler(commands=["autoexec"])
    def autoexec_cmd(m):

        if not has_permission(m, "autoexec"):
            bot.reply_to(m, "⛔ אין לך הרשאת autoexec")
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

                try:
                    r = subprocess.run(
                        ["bash", "-c", "\n".join(batch)],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )

                    if r.returncode:
                        output.append(
                            f"❌ BATCH FAILED\n{r.stderr}"
                        )
                        break

                    output.append(
                        f"✅ BATCH\n{r.stdout}"
                    )

                except Exception as e:
                    output.append(f"❌ {e}")

            elif line.startswith("/exec "):

                cmd = line[6:]

                try:
                    r = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=15
                    )

                    if r.returncode:
                        output.append(
                            f"❌ {cmd}\n{r.stderr}"
                        )
                        break

                    output.append(
                        f"✅ {cmd}\n{r.stdout}"
                    )

                except Exception as e:
                    output.append(f"❌ {cmd}\n{e}")

            i += 1


        bot.reply_to(
            m,
            "\n\n".join(output)[:4000]
            if output
            else "ℹ️ No commands found."
        )
