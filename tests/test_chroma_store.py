import tempfile
import unittest
from pathlib import Path

from tg_scrapper.chroma_store import (
    MESSAGES_COLLECTION,
    StoreItem,
    get_messages_collection,
    query_items,
    upsert_items,
)


class ChromaStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_item(self, item_id: str, embedding: list[float], **meta: object) -> StoreItem:
        return StoreItem(
            id=item_id,
            document=f"doc {item_id}",
            embedding=embedding,
            metadata={"chat_id": 1, "channel_name": "ch", "id": int(item_id.split(":")[-1]), **meta},
        )

    def test_upsert_and_query_returns_closest_first(self) -> None:
        collection = get_messages_collection(self.path)
        upsert_items(
            collection,
            [
                self.make_item("msg:1:1", [1.0, 0.0, 0.0, 0.0]),
                self.make_item("msg:1:2", [0.7, 0.7, 0.0, 0.0]),
                self.make_item("msg:1:3", [0.0, 1.0, 0.0, 0.0]),
            ],
        )

        hits = query_items(collection, [1.0, 0.0, 0.0, 0.0], top_k=2)

        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].id, "msg:1:1")
        self.assertLess(hits[0].distance, hits[1].distance)

    def test_collection_name_default(self) -> None:
        collection = get_messages_collection(self.path)
        self.assertEqual(collection.name, MESSAGES_COLLECTION)

    def test_include_embeddings_returns_vectors(self) -> None:
        collection = get_messages_collection(self.path)
        upsert_items(collection, [self.make_item("msg:1:1", [1.0, 0.0, 0.0, 0.0])])

        hits = query_items(
            collection,
            [1.0, 0.0, 0.0, 0.0],
            top_k=1,
            include_embeddings=True,
        )
        self.assertEqual(len(hits), 1)
        self.assertIsNotNone(hits[0].embedding)
        assert hits[0].embedding is not None
        self.assertEqual(len(hits[0].embedding), 4)

    def test_where_filter_metadata(self) -> None:
        collection = get_messages_collection(self.path)
        upsert_items(
            collection,
            [
                self.make_item("msg:1:1", [1.0, 0.0, 0.0, 0.0], date="2026-01-01", date_int=20260101),
                self.make_item("msg:1:2", [0.9, 0.1, 0.0, 0.0], date="2026-06-01", date_int=20260601),
            ],
        )

        hits = query_items(
            collection,
            [1.0, 0.0, 0.0, 0.0],
            top_k=5,
            where={"date_int": {"$gte": 20260501}},
        )
        self.assertEqual([hit.id for hit in hits], ["msg:1:2"])

    def test_none_metadata_is_dropped_on_upsert(self) -> None:
        collection = get_messages_collection(self.path)
        upsert_items(
            collection,
            [
                StoreItem(
                    id="msg:1:1",
                    document="doc",
                    embedding=[1.0, 0.0, 0.0, 0.0],
                    metadata={"chat_id": 1, "channel_name": None, "has_link": True},
                ),
            ],
        )

        hits = query_items(collection, [1.0, 0.0, 0.0, 0.0], top_k=1)
        self.assertNotIn("channel_name", hits[0].metadata)
        self.assertEqual(hits[0].metadata.get("has_link"), True)


if __name__ == "__main__":
    unittest.main()
