import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tg_scrapper.embed_messages import cli_main as embed_cli_main
from tg_scrapper.index_messages import cli_main as index_cli_main
from tg_scrapper.rag_query import cli_main as query_cli_main


class _FakeEncodedVectors:
    def __init__(self, vectors: list[list[float]]) -> None:
        self._vectors = vectors

    def tolist(self) -> list[list[float]]:
        return self._vectors


class _FakeSentenceTransformer:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def encode(self, texts: list[str], **_kwargs: object) -> _FakeEncodedVectors:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.casefold()
            if "proxmox" in lowered or "uefi" in lowered:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return _FakeEncodedVectors(vectors)


class SmokePipelineTests(unittest.TestCase):
    def test_fixture_messages_flow_through_embed_index_and_query(self) -> None:
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "messages_smoke.jsonl"

        with tempfile.TemporaryDirectory() as raw_dir:
            temp_dir = Path(raw_dir)
            embeddings_path = temp_dir / "messages.embeddings.jsonl"
            embed_state = temp_dir / "embed.state.json"
            index_state = temp_dir / "index.state.json"
            chroma_path = temp_dir / "chroma_db"
            output_path = temp_dir / "answer.md"

            with patch("tg_scrapper.embed_messages.SentenceTransformer", _FakeSentenceTransformer):
                embed_cli_main(
                    [
                        "--input",
                        str(fixture_path),
                        "--output",
                        str(embeddings_path),
                        "--state",
                        str(embed_state),
                        "--model",
                        "fake-model",
                        "--device",
                        "cpu",
                    ]
                )

            embedded_rows = [json.loads(line) for line in embeddings_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(embedded_rows), 2)

            index_cli_main(
                [
                    "--input",
                    str(embeddings_path),
                    "--state",
                    str(index_state),
                    "--chroma-path",
                    str(chroma_path),
                ]
            )

            def fake_llm(prompt: str) -> str:
                self.assertIn("Talos on Proxmox usually needs UEFI boot enabled.", prompt)
                self.assertNotIn("Kubernetes RBAC basics", prompt)
                return "Mocked Talos answer"

            with (
                patch("tg_scrapper.rag_query.SentenceTransformer", _FakeSentenceTransformer),
                patch("tg_scrapper.rag_query.build_openrouter_client", return_value=fake_llm),
            ):
                query_cli_main(
                    [
                        "--question",
                        "How should I run Talos on Proxmox?",
                        "--chroma-path",
                        str(chroma_path),
                        "--model",
                        "fake-model",
                        "--device",
                        "cpu",
                        "--no-expand",
                        "--top-k-per-query",
                        "1",
                        "--final-k",
                        "1",
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(output_path.read_text(encoding="utf-8"), "Mocked Talos answer\n")


if __name__ == "__main__":
    unittest.main()
