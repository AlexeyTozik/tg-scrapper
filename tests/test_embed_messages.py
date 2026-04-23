import unittest

from embed_messages import build_output_rows, get_target_batch_size


class BuildOutputRowsTests(unittest.TestCase):
    def test_carries_filtering_relevant_fields_into_embedding_output(self) -> None:
        message = {
            "id": 42,
            "chat_id": -1001,
            "channel_name": "Talos",
            "sender_id": 100,
            "date": "2026-03-14T10:00:00+00:00",
            "reply_to_msg_id": 10,
            "action_type": None,
            "media_type": "MessageMediaDocument",
            "has_media": True,
        }
        rows = build_output_rows([(7, message, "CPU=host")], [[0.1, 0.2, 0.3]], "./models/multilingual-e5-small")
        self.assertEqual(
            rows,
            [
                {
                    "id": 42,
                    "chat_id": -1001,
                    "channel_name": "Talos",
                    "sender_id": 100,
                    "date": "2026-03-14T10:00:00+00:00",
                    "reply_to_msg_id": 10,
                    "action_type": None,
                    "media_type": "MessageMediaDocument",
                    "has_media": True,
                    "text": "CPU=host",
                    "embedding_model": "./models/multilingual-e5-small",
                    "embedding_dim": 3,
                    "embedding": [0.1, 0.2, 0.3],
                }
            ],
        )

    def test_missing_optional_fields_are_serialized_as_none_or_false(self) -> None:
        message: dict[str, object] = {"id": 1}
        rows = build_output_rows([(1, message, "ceph")], [[0.5]], "model-id")
        self.assertEqual(rows[0]["chat_id"], None)
        self.assertEqual(rows[0]["channel_name"], None)
        self.assertEqual(rows[0]["sender_id"], None)
        self.assertEqual(rows[0]["reply_to_msg_id"], None)
        self.assertEqual(rows[0]["action_type"], None)
        self.assertEqual(rows[0]["media_type"], None)
        self.assertEqual(rows[0]["has_media"], False)


class GetTargetBatchSizeTests(unittest.TestCase):
    def test_batch_size_boundaries(self) -> None:
        cases = [
            (64, 0, 100, 64),
            (64, 10, 0, 10),
            (64, 10, 9, 1),
            (64, 10, 10, 0),
            (64, 10, 11, 0),
        ]

        for batch_size, max_messages, saved_embeddings, expected in cases:
            with self.subTest(
                batch_size=batch_size,
                max_messages=max_messages,
                saved_embeddings=saved_embeddings,
            ):
                self.assertEqual(
                    get_target_batch_size(batch_size, max_messages, saved_embeddings),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
