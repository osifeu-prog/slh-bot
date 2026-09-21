import unittest

from handlers.e_handler import normalize_python_command


class PythonCommandNormalizationTests(unittest.TestCase):
    def test_import_snippet_is_wrapped(self):
        self.assertEqual(
            normalize_python_command("import os; print(os.getcwd())"),
            "python3 -c 'import os; print(os.getcwd())'",
        )

    def test_from_snippet_is_wrapped(self):
        self.assertEqual(
            normalize_python_command("from pathlib import Path; print(Path.cwd())"),
            "python3 -c 'from pathlib import Path; print(Path.cwd())'",
        )

    def test_shell_commands_are_unchanged(self):
        self.assertEqual(normalize_python_command("pwd"), "pwd")


if __name__ == "__main__":
    unittest.main()
