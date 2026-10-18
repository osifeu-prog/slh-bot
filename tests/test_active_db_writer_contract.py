from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ActiveDbWriterContractTests(unittest.TestCase):
    def test_loaded_metadata_handlers_use_atomic_mutations(self):
        for relative in ("learning_path.py", "language_handler.py", "ton_handler.py"):
            with self.subTest(module=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("state_manager.atomic_update(", source)
                self.assertNotIn("state_manager.save_db(db)", source)

    def test_language_and_ton_handlers_are_loaded(self):
        loader = (ROOT / "handlers" / "loader.py").read_text(encoding="utf-8")
        self.assertIn('("ton", "ton_handler")', loader)
        self.assertIn("import language_handler", loader)
        self.assertIn("register_language(bot)", loader)
        self.assertIn('("learning_path", "learning_path")', loader)


if __name__ == "__main__":
    unittest.main()
