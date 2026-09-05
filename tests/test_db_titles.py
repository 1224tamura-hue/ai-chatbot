import os
import tempfile
import unittest

from database.db_manager import DatabaseManager


class ConversationTitleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "chatbot.db")
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_cleanup_keeps_one_empty_draft_across_languages(self):
        older = self.db.create_conversation("新しい会話")
        newer = self.db.create_conversation("New conversation")
        named = self.db.create_conversation("Keep me")

        self.db.cleanup_empty_conversations(title=("新しい会話", "New conversation"), keep=1)

        remaining = {conv["id"] for conv in self.db.get_all_conversations()}
        self.assertNotIn(older, remaining)
        self.assertIn(newer, remaining)
        self.assertIn(named, remaining)

    def test_auto_title_accepts_english_default(self):
        conversation_id = self.db.create_conversation("New conversation")
        self.db.add_message(conversation_id, "user", "What is the PTO deadline?")
        conversation = self.db.get_conversation(conversation_id)
        self.assertEqual(conversation["title"], "What is the PTO deadline")


if __name__ == "__main__":
    unittest.main()
