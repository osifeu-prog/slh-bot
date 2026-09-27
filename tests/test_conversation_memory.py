import unittest

from core.conversation_memory import is_continuation


class TestConversationMemory(unittest.TestCase):
    def test_hebrew_affirmations_are_continuations(self):
        for value in ("כן", "כן בבקשה", "המשך", "תמשיך", "בוא נמשיך"):
            self.assertTrue(is_continuation(value))

    def test_english_affirmations_are_continuations(self):
        for value in ("yes", "continue", "go on", "okay"):
            self.assertTrue(is_continuation(value))

    def test_normal_question_is_not_continuation(self):
        self.assertFalse(is_continuation("מה מצב הסטייקינג שלי?"))
