# ruff: noqa: RUF001

import unittest

from tg_scrapper.message_filter import (
    extract_message_text,
    get_filtered_message_text,
    has_technical_signal,
    is_short_chat_noise,
    normalize_short_chat_text,
    should_keep_message,
)


class ExtractMessageTextTests(unittest.TestCase):
    def test_prefers_text_and_strips_whitespace(self) -> None:
        row = {"text": "  CPU=host  ", "raw_text": "ignored"}
        self.assertEqual(extract_message_text(row), "CPU=host")

    def test_falls_back_to_raw_text(self) -> None:
        row = {"text": "   ", "raw_text": "  v1.10.3  "}
        self.assertEqual(extract_message_text(row), "v1.10.3")

    def test_returns_none_when_both_fields_blank(self) -> None:
        row = {"text": "   ", "raw_text": "\n\t "}
        self.assertIsNone(extract_message_text(row))


class NormalizeShortChatTextTests(unittest.TestCase):
    def test_normalizes_case_punctuation_and_yo(self) -> None:
        self.assertEqual(normalize_short_chat_text(" Ёж!!! "), "еж")

    def test_short_chat_noise_detection_handles_punctuation(self) -> None:
        positives = ["Спасибо!", "ОК", "  угу  ", "спасибо :)", "YES"]
        negatives = ["спасибо за пример", "ceph", "CPU=host"]

        for text in positives:
            with self.subTest(text=text):
                self.assertTrue(is_short_chat_noise(text))

        for text in negatives:
            with self.subTest(text=text):
                self.assertFalse(is_short_chat_noise(text))


class TechnicalSignalTests(unittest.TestCase):
    def test_detects_short_technical_text(self) -> None:
        positives = [
            "CPU=host",
            "v1.10.3",
            "1.7.5",
            "k8s",
            "ceph",
            "cni/cilium",
            "kube-apiserver",
            "containerd.sock",
            "mTLS",
        ]

        for text in positives:
            with self.subTest(text=text):
                self.assertTrue(has_technical_signal(text))

    def test_rejects_nontechnical_short_text(self) -> None:
        negatives = [
            "да/нет",
            "что-то",
            "угу",
            "спасибо",
            "123",
            "??",
        ]

        for text in negatives:
            with self.subTest(text=text):
                self.assertFalse(has_technical_signal(text))


class MessageFilterTests(unittest.TestCase):
    def base_row(self) -> dict[str, object]:
        return {
            "id": 1,
            "text": "Hello world, this is a sufficiently long test message.",
            "raw_text": "Hello world, this is a sufficiently long test message.",
            "reply_to_msg_id": None,
            "action_type": None,
        }

    def test_long_message_is_kept(self) -> None:
        self.assertTrue(should_keep_message(self.base_row(), min_chars=20))

    def test_message_exactly_at_threshold_is_kept(self) -> None:
        row = self.base_row()
        row["text"] = "12345678901234567890"
        row["raw_text"] = "12345678901234567890"
        self.assertTrue(should_keep_message(row, min_chars=20))

    def test_service_message_is_rejected_even_if_technical(self) -> None:
        row = self.base_row()
        row["text"] = "CPU=host"
        row["raw_text"] = "CPU=host"
        row["action_type"] = "MessageActionChatAddUser"
        self.assertFalse(should_keep_message(row, min_chars=20))

    def test_empty_media_only_message_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = ""
        row["raw_text"] = ""
        row["media_type"] = "MessageMediaPhoto"
        self.assertIsNone(get_filtered_message_text(row, min_chars=20))

    def test_emoji_only_message_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "🤣"
        row["raw_text"] = "🤣"
        self.assertFalse(should_keep_message(row, min_chars=1))

    def test_punctuation_only_message_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "?!..--"
        row["raw_text"] = "?!..--"
        self.assertFalse(should_keep_message(row, min_chars=1))

    def test_short_stoplist_message_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "Спасибо!"
        row["raw_text"] = "Спасибо!"
        self.assertFalse(should_keep_message(row, min_chars=20))

    def test_short_stoplist_reply_is_still_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "ОК"
        row["raw_text"] = "ОК"
        row["reply_to_msg_id"] = 42
        self.assertFalse(should_keep_message(row, min_chars=20))

    def test_short_reply_is_kept(self) -> None:
        row = self.base_row()
        row["text"] = "Смотри выше"
        row["raw_text"] = "Смотри выше"
        row["reply_to_msg_id"] = 42
        self.assertEqual(get_filtered_message_text(row, min_chars=20), "Смотри выше")

    def test_short_technical_message_is_kept(self) -> None:
        row = self.base_row()
        row["text"] = "CPU=host"
        row["raw_text"] = "CPU=host"
        self.assertEqual(get_filtered_message_text(row, min_chars=20), "CPU=host")

    def test_short_latin_token_is_kept(self) -> None:
        row = self.base_row()
        row["text"] = "ceph"
        row["raw_text"] = "ceph"
        self.assertEqual(get_filtered_message_text(row, min_chars=20), "ceph")

    def test_short_cyrillic_hyphen_text_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "что-то"
        row["raw_text"] = "что-то"
        self.assertIsNone(get_filtered_message_text(row, min_chars=20))

    def test_short_cyrillic_slash_text_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "да/нет"
        row["raw_text"] = "да/нет"
        self.assertIsNone(get_filtered_message_text(row, min_chars=20))

    def test_raw_text_fallback_is_used(self) -> None:
        row = self.base_row()
        row["text"] = None
        row["raw_text"] = "v1.10.3"
        self.assertEqual(get_filtered_message_text(row, min_chars=20), "v1.10.3")

    def test_short_plain_number_is_rejected(self) -> None:
        row = self.base_row()
        row["text"] = "123"
        row["raw_text"] = "123"
        self.assertIsNone(get_filtered_message_text(row, min_chars=20))


if __name__ == "__main__":
    unittest.main()
