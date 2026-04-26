import unittest

from tg_scrapper.query_expansion import extract_json_array


class ExtractJsonArrayTests(unittest.TestCase):
    def test_plain_json(self) -> None:
        self.assertEqual(extract_json_array('["a", "b"]'), ["a", "b"])

    def test_with_code_fences(self) -> None:
        payload = '```json\n["a", "b"]\n```'
        self.assertEqual(extract_json_array(payload), ["a", "b"])

    def test_invalid_returns_empty(self) -> None:
        self.assertEqual(extract_json_array("not json"), [])

    def test_non_list_returns_empty(self) -> None:
        self.assertEqual(extract_json_array('{"a": 1}'), [])

    def test_filters_blank_items(self) -> None:
        self.assertEqual(extract_json_array('["a", "", "   "]'), ["a"])


if __name__ == "__main__":
    unittest.main()
