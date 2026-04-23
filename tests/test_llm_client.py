import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from openai import APIStatusError

import app_support
import llm_client


class GetApiKeyTests(unittest.TestCase):
    def test_uses_openrouter_key(self) -> None:
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "openrouter-key"}, clear=True):
            self.assertEqual(llm_client.get_api_key(), "openrouter-key")

    def test_falls_back_to_openai_key(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai-key"}, clear=True):
            self.assertEqual(llm_client.get_api_key(), "openai-key")

    def test_requires_an_api_key(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY is not set"),
        ):
            llm_client.get_api_key()


class LoadRepoDotenvTests(unittest.TestCase):
    def test_overrides_existing_shell_env(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            temp_path = Path(raw_dir)
            (temp_path / ".env").write_text("OPENROUTER_API_KEY=fresh-key\n", encoding="utf-8")

            with (
                patch.object(app_support, "REPO_ROOT", temp_path),
                patch.dict(os.environ, {"OPENROUTER_API_KEY": "stale-key"}, clear=False),
            ):
                app_support.load_repo_dotenv()
                self.assertEqual(os.environ["OPENROUTER_API_KEY"], "fresh-key")


class CallWithRetriesTests(unittest.TestCase):
    def _request(self) -> httpx.Request:
        return httpx.Request("POST", "https://openrouter.ai/api/v1/responses")

    def test_retries_status_errors(self) -> None:
        attempts = {"count": 0}
        sleeps: list[float] = []

        def flaky(prompt: str) -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise APIStatusError("busy", response=httpx.Response(503, request=self._request()), body={})
            return f"ok::{prompt}"

        result = llm_client.call_with_retries(
            "prompt",
            flaky,
            sleep_fn=sleeps.append,
            max_attempts=4,
            base_delay_seconds=0.5,
        )

        self.assertEqual(result, "ok::prompt")
        self.assertEqual(sleeps, [0.5, 1.0])

    def test_does_not_retry_non_retryable_errors(self) -> None:
        def broken(_: str) -> str:
            raise ValueError("bad prompt")

        with self.assertRaisesRegex(ValueError, "bad prompt"):
            llm_client.call_with_retries("prompt", broken, sleep_fn=lambda _: None)

    def test_raises_retryable_wrapper_after_exhausting_attempts(self) -> None:
        def always_busy(_: str) -> str:
            raise APIStatusError("busy", response=httpx.Response(503, request=self._request()), body={})

        with self.assertRaises(llm_client.RetryableLLMError) as exc_info:
            llm_client.call_with_retries(
                "prompt",
                always_busy,
                sleep_fn=lambda _: None,
                max_attempts=2,
                base_delay_seconds=0.01,
            )

        self.assertEqual(exc_info.exception.attempts, 2)
        self.assertIsInstance(exc_info.exception.cause, APIStatusError)


class BuildOpenRouterClientTests(unittest.TestCase):
    @patch("llm_client.OpenAI")
    def test_passes_base_url_and_strips_response(self, openai_cls: Mock) -> None:
        client = openai_cls.return_value
        client.responses.create.return_value.output_text = " openrouter answer "

        call = llm_client.build_openrouter_client(
            model="openai/gpt-oss-120b:free",
            api_key="openrouter-key",
            base_url="https://openrouter.ai/api/v1",
        )
        text = call("prompt text")

        self.assertEqual(text, "openrouter answer")
        openai_cls.assert_called_once_with(api_key="openrouter-key", base_url="https://openrouter.ai/api/v1")
        client.responses.create.assert_called_once_with(model="openai/gpt-oss-120b:free", input="prompt text")

    @patch("llm_client.OpenAI")
    def test_raises_on_empty_response(self, openai_cls: Mock) -> None:
        client = openai_cls.return_value
        client.responses.create.return_value.output_text = "   "

        call = llm_client.build_openrouter_client(
            model="m",
            api_key="k",
            base_url="https://example.com",
        )
        with self.assertRaisesRegex(RuntimeError, "empty response"):
            call("prompt")


if __name__ == "__main__":
    unittest.main()
