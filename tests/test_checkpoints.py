import json
import tempfile
import unittest
from pathlib import Path

from tg_scrapper.checkpoints import load_checkpoint, save_checkpoint


class CheckpointTests(unittest.TestCase):
    def test_load_returns_default_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            path = Path(raw_dir) / "state.json"

            self.assertEqual(load_checkpoint(path, {"processed_lines": 0}), {"processed_lines": 0})

    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            path = Path(raw_dir) / "nested" / "state.json"

            save_checkpoint(path, {"processed_files": {"a.jsonl": 10}})

            self.assertEqual(load_checkpoint(path, {}), {"processed_files": {"a.jsonl": 10}})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"processed_files": {"a.jsonl": 10}})


if __name__ == "__main__":
    unittest.main()
