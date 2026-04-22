import argparse
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from openai import APIStatusError

import app_support
import summarize_jsonl


class SummarizeJsonlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.prompt_path = self.temp_path / "prompt.txt"
        self.prompt_path.write_text(
            "group={group_key_name}:{group_key_value}\ncount={message_count}\n{transcript}",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_args(self, input_path: Path, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "model": "test-model",
            "input_file": str(input_path),
            "output_file": None,
            "prompt_file": str(self.prompt_path),
            "messages_field": "messages",
            "key_field": None,
            "base_url": summarize_jsonl.DEFAULT_OPENROUTER_BASE_URL,
            "overwrite": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_detect_key_field_auto_detects_day(self) -> None:
        row: dict[str, object] = {"day": "2024-09-13", "messages": []}
        self.assertEqual(summarize_jsonl.detect_key_field(row, "messages", None), "day")

    def test_detect_key_field_auto_detects_thread_id(self) -> None:
        row: dict[str, object] = {"thread_id": 123, "messages": []}
        self.assertEqual(summarize_jsonl.detect_key_field(row, "messages", None), "thread_id")

    def test_detect_key_field_rejects_ambiguous_row(self) -> None:
        row: dict[str, object] = {"day": "2024-09-13", "thread_id": 123, "messages": []}
        with self.assertRaisesRegex(ValueError, "Could not auto-detect"):
            summarize_jsonl.detect_key_field(row, "messages", None)

    def test_build_transcript_uses_text_raw_text_and_action(self) -> None:
        messages: list[dict[str, object]] = [
            {"text": "  hello  ", "raw_text": "ignored", "date": "2024-01-01T00:00:00Z", "sender_id": 1},
            {"text": "", "raw_text": " fallback ", "sender_id": 2},
            {"text": "", "raw_text": "", "action_type": "MessageActionGroupCall"},
            {"text": "", "raw_text": "", "media_type": "MessageMediaPhoto"},
        ]

        transcript = summarize_jsonl.build_transcript(messages)

        self.assertIn("hello", transcript)
        self.assertIn("fallback", transcript)
        self.assertIn("[SYSTEM_EVENT: MessageActionGroupCall]", transcript)
        self.assertNotIn("MessageMediaPhoto", transcript)

    def test_make_output_path_uses_summary_suffix(self) -> None:
        input_path = Path("days.jsonl")
        output_path = summarize_jsonl.make_output_path(input_path, None)
        self.assertEqual(output_path, Path("days_summary.jsonl"))

    def test_get_api_key_uses_openrouter_key(self) -> None:
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "openrouter-key"}, clear=True):
            self.assertEqual(summarize_jsonl.get_api_key(), "openrouter-key")

    def test_get_api_key_falls_back_to_openai_key(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai-key"}, clear=True):
            self.assertEqual(summarize_jsonl.get_api_key(), "openai-key")

    def test_get_api_key_requires_openrouter_key(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY is not set"),
        ):
            summarize_jsonl.get_api_key()

    def test_load_environment_overrides_existing_shell_env(self) -> None:
        (self.temp_path / ".env").write_text("OPENROUTER_API_KEY=fresh-key\n", encoding="utf-8")

        with (
            patch.object(app_support, "REPO_ROOT", self.temp_path),
            patch.dict(os.environ, {"OPENROUTER_API_KEY": "stale-key"}, clear=False),
        ):
            app_support.load_repo_dotenv()
            self.assertEqual(os.environ["OPENROUTER_API_KEY"], "fresh-key")

    def test_summarize_with_retries_retries_status_errors(self) -> None:
        attempts = {"count": 0}
        sleeps: list[float] = []
        request = httpx.Request("POST", "https://openrouter.ai/api/v1/responses")

        def flaky(prompt: str) -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise APIStatusError("busy", response=httpx.Response(503, request=request), body={})
            return f"ok::{prompt}"

        result = summarize_jsonl.summarize_with_retries(
            "prompt",
            flaky,
            sleep_fn=sleeps.append,
            max_attempts=4,
            base_delay_seconds=0.5,
        )

        self.assertEqual(result, "ok::prompt")
        self.assertEqual(sleeps, [0.5, 1.0])

    def test_summarize_with_retries_does_not_retry_non_retryable_errors(self) -> None:
        def broken(_: str) -> str:
            raise ValueError("bad prompt")

        with self.assertRaisesRegex(ValueError, "bad prompt"):
            summarize_jsonl.summarize_with_retries("prompt", broken, sleep_fn=lambda _: None)

    def test_summarize_with_retries_raises_retryable_wrapper_after_exhausting_attempts(self) -> None:
        request = httpx.Request("POST", "https://openrouter.ai/api/v1/responses")

        def always_busy(_: str) -> str:
            raise APIStatusError("busy", response=httpx.Response(503, request=request), body={})

        with self.assertRaises(summarize_jsonl.RetryableLLMError) as exc_info:
            summarize_jsonl.summarize_with_retries(
                "prompt",
                always_busy,
                sleep_fn=lambda _: None,
                max_attempts=2,
                base_delay_seconds=0.01,
            )

        self.assertEqual(exc_info.exception.attempts, 2)
        self.assertIsInstance(exc_info.exception.cause, APIStatusError)

    def test_summarize_rows_writes_placeholder_without_calling_model(self) -> None:
        input_path = self.temp_path / "days.jsonl"
        app_support.write_jsonl(
            input_path,
            [
                {
                    "day": "2024-09-13",
                    "messages": [
                        {"text": "", "raw_text": "", "media_type": "MessageMediaPhoto"},
                        {"text": None, "raw_text": None, "media_type": "MessageMediaDocument"},
                    ],
                }
            ],
        )
        args = self.make_args(input_path)
        fake_summarizer = Mock(return_value="should not be used")

        summarize_jsonl.summarize_rows(args, summarize_fn=fake_summarizer)

        output_path = self.temp_path / "days_summary.jsonl"
        rows = app_support.read_jsonl(output_path)
        self.assertEqual(rows[0]["summary"], summarize_jsonl.NO_CONTENT_SUMMARY)
        fake_summarizer.assert_not_called()

    def test_summarize_rows_resume_skips_processed_keys(self) -> None:
        input_path = self.temp_path / "days.jsonl"
        output_path = self.temp_path / "days_summary.jsonl"
        app_support.write_jsonl(
            input_path,
            [
                {"day": "2024-09-13", "messages": [{"text": "first", "raw_text": "", "sender_id": 1}]},
                {"day": "2024-09-14", "messages": [{"text": "second", "raw_text": "", "sender_id": 1}]},
            ],
        )
        app_support.write_jsonl(
            output_path,
            [
                {
                    "day": "2024-09-13",
                    "summary": "existing summary",
                    "provider": "openrouter",
                    "model": "old-model",
                }
            ],
        )

        args = self.make_args(input_path, output_file=str(output_path))
        fake_summarizer = Mock(return_value="new summary")

        summarize_jsonl.summarize_rows(args, summarize_fn=fake_summarizer)

        rows = app_support.read_jsonl(output_path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["day"], "2024-09-13")
        self.assertEqual(rows[1]["day"], "2024-09-14")
        fake_summarizer.assert_called_once()

    def test_summarize_rows_overwrite_replaces_existing_output(self) -> None:
        input_path = self.temp_path / "threads.jsonl"
        output_path = self.temp_path / "threads_summary.jsonl"
        app_support.write_jsonl(
            input_path,
            [
                {"thread_id": 1, "messages": [{"text": "fresh text", "raw_text": "", "sender_id": 1}]},
            ],
        )
        app_support.write_jsonl(
            output_path,
            [
                {
                    "thread_id": 999,
                    "summary": "stale summary",
                    "provider": "openrouter",
                    "model": "old-model",
                }
            ],
        )

        args = self.make_args(input_path, output_file=str(output_path), overwrite=True)

        summarize_jsonl.summarize_rows(args, summarize_fn=lambda prompt: f"summary::{prompt.splitlines()[0]}")

        rows = app_support.read_jsonl(output_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["thread_id"], 1)
        self.assertNotEqual(rows[0]["summary"], "stale summary")

    @patch("summarize_jsonl.summarize_with_retries")
    def test_summarize_rows_stops_cleanly_on_retryable_exhaustion(self, retry_mock: Mock) -> None:
        input_path = self.temp_path / "days.jsonl"
        output_path = self.temp_path / "days_summary.jsonl"
        app_support.write_jsonl(
            input_path,
            [
                {"day": "2024-09-13", "messages": [{"text": "first", "raw_text": "", "sender_id": 1}]},
                {"day": "2024-09-14", "messages": [{"text": "second", "raw_text": "", "sender_id": 1}]},
            ],
        )
        retry_mock.side_effect = [
            "summary one",
            summarize_jsonl.RetryableLLMError(
                APIStatusError(
                    "quota",
                    response=httpx.Response(
                        429,
                        request=httpx.Request("POST", "https://openrouter.ai/api/v1/responses"),
                    ),
                    body={},
                ),
                5,
            ),
        ]

        args = self.make_args(input_path, output_file=str(output_path))

        summarize_jsonl.summarize_rows(args, summarize_fn=lambda prompt: prompt)

        rows = app_support.read_jsonl(output_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["day"], "2024-09-13")

    @patch("summarize_jsonl.OpenAI")
    def test_build_openrouter_summarizer_passes_base_url(self, openai_cls: Mock) -> None:
        client = openai_cls.return_value
        client.responses.create.return_value.output_text = " openrouter summary "

        summarize = summarize_jsonl.build_openrouter_summarizer(
            model="openai/gpt-oss-120b:free",
            api_key="openrouter-key",
            base_url="https://openrouter.ai/api/v1",
        )
        summary = summarize("prompt text")

        self.assertEqual(summary, "openrouter summary")
        openai_cls.assert_called_once_with(api_key="openrouter-key", base_url="https://openrouter.ai/api/v1")
        client.responses.create.assert_called_once_with(model="openai/gpt-oss-120b:free", input="prompt text")


if __name__ == "__main__":
    unittest.main()
