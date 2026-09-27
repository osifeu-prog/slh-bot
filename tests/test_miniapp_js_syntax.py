"""Validate every inline Mini App script with Node's parser."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which("node"), "node not installed")
class MiniAppJsSyntaxTest(unittest.TestCase):
    def test_all_inline_scripts_parse(self):
        src = Path("mini_app.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script(?:\s[^>]*)?>([\\s\\S]*?)</script>", src, flags=re.IGNORECASE)
        self.assertTrue(scripts)
        for index, code in enumerate(scripts):
            with tempfile.NamedTemporaryFile(
                "w", suffix=".js", delete=False, encoding="utf-8"
            ) as handle:
                handle.write(code)
                temp_path = handle.name
            try:
                result = subprocess.run(
                    ["node", "--check", temp_path],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"inline script #{index} has a syntax error:\\n{result.stderr[:1000]}",
                )
            finally:
                Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
