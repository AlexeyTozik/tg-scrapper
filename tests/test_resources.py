import tempfile
import unittest
from pathlib import Path

from tg_scrapper.resources import get_packaged_prompt_text, read_prompt_text


class PackagedPromptTests(unittest.TestCase):
    def test_loads_packaged_multi_query_prompt(self) -> None:
        prompt = get_packaged_prompt_text("multi_query.txt")
        self.assertTrue(prompt.strip())
        self.assertIn("{question}", prompt)

    def test_explicit_path_overrides_packaged_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            path = Path(raw_dir) / "prompt.txt"
            path.write_text("custom prompt", encoding="utf-8")
            self.assertEqual(read_prompt_text(str(path), default_filename="multi_query.txt"), "custom prompt")


if __name__ == "__main__":
    unittest.main()
