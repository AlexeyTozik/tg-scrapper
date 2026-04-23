# ruff: noqa: RUF001

import unittest

from index_messages import build_item, build_metadata, extract_date


class ExtractDateTests(unittest.TestCase):
    def test_iso_timestamp(self) -> None:
        self.assertEqual(extract_date({"date": "2026-03-14T10:00:00+00:00"}), "2026-03-14")

    def test_date_only(self) -> None:
        self.assertEqual(extract_date({"date": "2026-03-14"}), "2026-03-14")

    def test_missing_date(self) -> None:
        self.assertIsNone(extract_date({}))


class BuildItemTests(unittest.TestCase):
    def base_row(self) -> dict[str, object]:
        return {
            "id": 42,
            "chat_id": -1001,
            "channel_name": "Ch",
            "sender_id": 100,
            "date": "2026-03-14T10:00:00+00:00",
            "text": "Hello world, this is a sufficiently long test message.",
            "embedding": [0.1] * 4,
        }

    def test_valid_row_produces_item(self) -> None:
        item = build_item(self.base_row(), min_chars=20)
        assert item is not None
        self.assertEqual(item.id, "msg:-1001:42")
        self.assertIn("Hello world", item.document)
        self.assertEqual(item.metadata.get("chat_id"), -1001)
        self.assertEqual(item.metadata.get("channel_name"), "Ch")
        self.assertEqual(item.metadata.get("date"), "2026-03-14")
        self.assertEqual(item.metadata.get("date_int"), 20260314)
        self.assertEqual(item.metadata.get("has_link"), False)

    def test_short_text_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "дай ссылку"
        self.assertIsNone(build_item(row, min_chars=20))

    def test_empty_text_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = ""
        self.assertIsNone(build_item(row, min_chars=20))

    def test_emoji_only_text_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "!!!......???"
        self.assertIsNone(build_item(row, min_chars=1))

    def test_short_reply_is_kept(self) -> None:
        row = self.base_row()
        row["text"] = "Смотри выше"
        row["reply_to_msg_id"] = 10
        item = build_item(row, min_chars=20)
        assert item is not None
        self.assertEqual(item.document, "Смотри выше")

    def test_short_technical_text_is_kept(self) -> None:
        row = self.base_row()
        row["text"] = "CPU=host"
        item = build_item(row, min_chars=20)
        assert item is not None
        self.assertEqual(item.document, "CPU=host")

    def test_short_latin_token_is_kept(self) -> None:
        row = self.base_row()
        row["text"] = "ceph"
        item = build_item(row, min_chars=20)
        assert item is not None
        self.assertEqual(item.document, "ceph")

    def test_service_message_is_rejected(self) -> None:
        row = self.base_row()
        row["action_type"] = "MessageActionChatAddUser"
        self.assertIsNone(build_item(row, min_chars=20))

    def test_short_stoplist_reply_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "ОК"
        row["reply_to_msg_id"] = 10
        self.assertIsNone(build_item(row, min_chars=20))

    def test_short_cyrillic_slash_text_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "да/нет"
        self.assertIsNone(build_item(row, min_chars=20))

    def test_raw_text_fallback_is_supported(self) -> None:
        row = self.base_row()
        row["text"] = None
        row["raw_text"] = "v1.10.3"
        item = build_item(row, min_chars=20)
        assert item is not None
        self.assertEqual(item.document, "v1.10.3")

    def test_missing_embedding_is_rejected(self) -> None:
        row = self.base_row()
        row.pop("embedding")
        self.assertIsNone(build_item(row, min_chars=20))

    def test_has_link_detected(self) -> None:
        row = self.base_row()
        row["text"] = "Check https://example.com for Talos best practices details."
        item = build_item(row, min_chars=20)
        assert item is not None
        self.assertEqual(item.metadata.get("has_link"), True)

    def test_unknown_chat_id_still_builds(self) -> None:
        row = self.base_row()
        row.pop("chat_id")
        item = build_item(row, min_chars=20)
        assert item is not None
        self.assertTrue(item.id.startswith("msg:unknown:"))


class BuildMetadataTests(unittest.TestCase):
    def test_uses_raw_text_fallback_for_length_and_link_detection(self) -> None:
        row: dict[str, object] = {
            "id": 42,
            "text": None,
            "raw_text": "  see https://example.com/v1.10.3  ",
            "date": "2026-03-14T10:00:00+00:00",
        }
        metadata = build_metadata(row)
        self.assertEqual(metadata["text_length"], len("see https://example.com/v1.10.3"))
        self.assertEqual(metadata["has_link"], True)
        self.assertEqual(metadata["date"], "2026-03-14")
        self.assertEqual(metadata["date_int"], 20260314)


if __name__ == "__main__":
    unittest.main()
