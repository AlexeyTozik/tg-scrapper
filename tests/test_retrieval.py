import argparse
import unittest

from tg_scrapper.chroma_store import QueryHit
from tg_scrapper.retrieval import build_where_filter, format_context, merge_hits, mmr_rerank


def make_hit(
    hit_id: str,
    distance: float,
    embedding: list[float] | None = None,
    **meta: object,
) -> QueryHit:
    return QueryHit(
        id=hit_id,
        document=f"doc {hit_id}",
        metadata={"chat_id": 1, "channel_name": "ch", "id": int(hit_id.split(":")[-1]), **meta},
        distance=distance,
        embedding=embedding,
    )


class MergeHitsTests(unittest.TestCase):
    def test_merges_by_id_keeping_min_distance(self) -> None:
        list_a = [make_hit("msg:1:1", 0.5), make_hit("msg:1:2", 0.9)]
        list_b = [make_hit("msg:1:1", 0.2), make_hit("msg:1:3", 0.4)]

        merged = merge_hits([list_a, list_b])
        ids = [hit.id for hit in merged]

        self.assertEqual(ids, ["msg:1:1", "msg:1:3", "msg:1:2"])
        self.assertEqual(merged[0].distance, 0.2)


class MmrRerankTests(unittest.TestCase):
    def test_prefers_diversity(self) -> None:
        hits = [
            make_hit("msg:1:1", 0.1, embedding=[1.0, 0.0]),
            make_hit("msg:1:2", 0.11, embedding=[1.0, 0.0]),
            make_hit("msg:1:3", 0.3, embedding=[0.0, 1.0]),
        ]
        result = mmr_rerank(hits, final_k=2, lambda_mult=0.5)

        self.assertEqual(result[0].id, "msg:1:1")
        self.assertEqual(result[1].id, "msg:1:3")

    def test_falls_back_when_no_embeddings(self) -> None:
        hits = [make_hit("msg:1:1", 0.1), make_hit("msg:1:2", 0.2)]
        result = mmr_rerank(hits, final_k=1, lambda_mult=0.5)
        self.assertEqual(len(result), 1)


class BuildWhereFilterTests(unittest.TestCase):
    def make_args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "since": None,
            "until": None,
            "channels": None,
            "chat_ids": None,
            "with_links_only": False,
            "min_chars": 0,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_no_filters_returns_none(self) -> None:
        self.assertIsNone(build_where_filter(self.make_args()))

    def test_single_filter_returned_flat(self) -> None:
        filter_expr = build_where_filter(self.make_args(since="2026-01-01"))
        self.assertEqual(filter_expr, {"date_int": {"$gte": 20260101}})

    def test_multiple_filters_combined_with_and(self) -> None:
        filter_expr = build_where_filter(
            self.make_args(
                since="2026-01-01",
                until="2026-12-31",
                channels="Ch A, Ch B",
                with_links_only=True,
                min_chars=20,
            )
        )
        assert filter_expr is not None
        self.assertIn("$and", filter_expr)
        clauses = filter_expr["$and"]
        self.assertIn({"date_int": {"$gte": 20260101}}, clauses)
        self.assertIn({"date_int": {"$lte": 20261231}}, clauses)
        self.assertIn({"channel_name": {"$in": ["Ch A", "Ch B"]}}, clauses)
        self.assertIn({"has_link": True}, clauses)
        self.assertIn({"text_length": {"$gte": 20}}, clauses)


class FormatContextTests(unittest.TestCase):
    def test_renders_header_and_document(self) -> None:
        hit = make_hit("msg:1:42", 0.1, date="2026-03-14", channel_name="Ch")
        rendered = format_context([hit])
        self.assertIn("[#1]", rendered)
        self.assertIn("channel=Ch", rendered)
        self.assertIn("msg_id=42", rendered)
        self.assertIn("date=2026-03-14", rendered)
        self.assertIn("doc msg:1:42", rendered)


if __name__ == "__main__":
    unittest.main()
