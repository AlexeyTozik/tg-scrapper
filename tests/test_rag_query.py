import tempfile
import unittest
from pathlib import Path

from tg_scrapper.rag_query import QueryConfig, parse_args, resolve_output_path


class ResolveOutputPathTests(unittest.TestCase):
    def test_explicit_output_wins(self) -> None:
        config = QueryConfig.from_args(parse_args(["--question", "q", "--output", "answer.md"]))
        self.assertEqual(resolve_output_path(config), Path("answer.md"))

    def test_default_output_uses_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            config = QueryConfig.from_args(parse_args(["--question", "q", "--output-dir", raw_dir]))
            output = resolve_output_path(config)

        self.assertEqual(output.parent, Path(raw_dir))
        self.assertEqual(output.suffix, ".md")


if __name__ == "__main__":
    unittest.main()
