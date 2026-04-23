import logging
import time
from collections.abc import Callable

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from app_support import get_first_env

LLMCallFn = Callable[[str], str]

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_RETRY_ATTEMPTS = 5
BASE_RETRY_DELAY_SECONDS = 2.0


class RetryableLLMError(RuntimeError):
    def __init__(self, cause: Exception, attempts: int):
        self.cause = cause
        self.attempts = attempts
        super().__init__(f"LLM request failed after {attempts} retry attempts: {cause}")


def get_api_key() -> str:
    api_key = get_first_env("OPENROUTER_API_KEY", "OPENAI_API_KEY")
    if api_key:
        return api_key
    raise RuntimeError(
        "OPENROUTER_API_KEY is not set. Add it to .env or the environment. Legacy OPENAI_API_KEY is also accepted."
    )


def is_retryable_error(error: Exception) -> bool:
    if isinstance(error, APIConnectionError | RateLimitError):
        return True

    if isinstance(error, APIStatusError):
        return error.status_code in {408, 409, 429} or error.status_code >= 500

    return False


def call_with_retries(
    prompt: str,
    call_fn: LLMCallFn,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_attempts: int = MAX_RETRY_ATTEMPTS,
    base_delay_seconds: float = BASE_RETRY_DELAY_SECONDS,
) -> str:
    attempt = 1

    while True:
        try:
            return call_fn(prompt)
        except Exception as error:
            if not is_retryable_error(error):
                raise

            if attempt >= max_attempts:
                raise RetryableLLMError(error, attempt) from error

            delay_seconds = base_delay_seconds * (2 ** (attempt - 1))
            logging.warning(
                "LLM request failed on attempt %s/%s with %s. Retrying in %.1f seconds.",
                attempt,
                max_attempts,
                error,
                delay_seconds,
            )
            sleep_fn(delay_seconds)
            attempt += 1


def build_openrouter_client(model: str, api_key: str, base_url: str) -> LLMCallFn:
    client = OpenAI(api_key=api_key, base_url=base_url)

    def call(prompt: str) -> str:
        response = client.responses.create(model=model, input=prompt)
        text = response.output_text
        if not text or not text.strip():
            raise RuntimeError("LLM returned an empty response")
        return text.strip()

    return call
