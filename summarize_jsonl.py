import argparse
import json
import logging
import time
from collections.abc import Callable
from itertools import chain
from pathlib import Path

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from app_support import (
    JsonObject,
    ensure_json_object,
    get_first_env,
    get_optional_int,
    get_optional_str,
    iter_jsonl,
    load_repo_dotenv,
)

SummarizeFn = Callable[[str], str]
NO_CONTENT_SUMMARY = "Нет текстового содержания для резюмирования."
MAX_RETRY_ATTEMPTS = 5
BASE_RETRY_DELAY_SECONDS = 2.0
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OUTPUT_PROVIDER = "openrouter"


class RetryableLLMError(RuntimeError):
    def __init__(self, cause: Exception, attempts: int):
        self.cause = cause
        self.attempts = attempts
        super().__init__(f"LLM request failed after {attempts} retry attempts: {cause}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize grouped JSONL rows with OpenRouter models.")
    parser.add_argument("--model", required=True, help="OpenRouter model name, for example openai/gpt-oss-120b:free")
    parser.add_argument("--input-file", required=True, help="Input JSONL file with grouped rows")
    parser.add_argument("--output-file", help="Output JSONL file; defaults to <input_stem>_summary.jsonl")
    parser.add_argument(
        "--prompt-file",
        default="prompts/summarize_group.txt",
        help="Path to the prompt template file",
    )
    parser.add_argument(
        "--messages-field",
        default="messages",
        help='Name of the field that contains grouped messages, default: "messages"',
    )
    parser.add_argument(
        "--key-field",
        help="Name of the top-level key to preserve; auto-detected if omitted",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_OPENROUTER_BASE_URL,
        help=f"OpenRouter-compatible base URL, default: {DEFAULT_OPENROUTER_BASE_URL}",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file instead of resuming from existing rows",
    )
    return parser.parse_args()


def get_key_value(row: JsonObject, key_field: str) -> object:
    if key_field not in row:
        raise ValueError(f'Missing key field "{key_field}" in input row')
    return row[key_field]


def get_messages(row: JsonObject, messages_field: str) -> list[JsonObject]:
    raw_messages = row.get(messages_field)
    if not isinstance(raw_messages, list):
        raise ValueError(f'Field "{messages_field}" must be a list of message objects')

    return [
        ensure_json_object(raw_message, f'Message #{index} in field "{messages_field}"')
        for index, raw_message in enumerate(raw_messages, start=1)
    ]


def detect_key_field(row: JsonObject, messages_field: str, explicit_key_field: str | None) -> str:
    if explicit_key_field is not None:
        if explicit_key_field == messages_field:
            raise ValueError("--key-field must be different from --messages-field")
        if explicit_key_field not in row:
            raise ValueError(f'Explicit key field "{explicit_key_field}" is missing in the input row')
        return explicit_key_field

    candidate_fields = [key for key in row if key != messages_field]
    if len(candidate_fields) != 1:
        raise ValueError(
            "Could not auto-detect the key field. Pass --key-field explicitly when the input row "
            f"contains fields: {', '.join(sorted(row))}"
        )
    return candidate_fields[0]


def make_output_path(input_path: Path, output_file: str | None) -> Path:
    if output_file is not None:
        return Path(output_file)
    return input_path.with_name(f"{input_path.stem}_summary.jsonl")


def canonicalize_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_processed_keys(output_path: Path, key_field: str) -> set[str]:
    if not output_path.exists():
        return set()

    processed_keys: set[str] = set()
    for _, row in iter_jsonl(output_path):
        processed_keys.add(canonicalize_key(get_key_value(row, key_field)))
    return processed_keys


def stringify_value(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def extract_message_content(message: JsonObject) -> str | None:
    for field in ("text", "raw_text"):
        value = get_optional_str(message, field)
        if value is not None:
            cleaned = value.strip()
            if cleaned:
                return cleaned

    action_type = get_optional_str(message, "action_type")
    if action_type:
        return f"[SYSTEM_EVENT: {action_type}]"

    return None


def build_transcript(messages: list[JsonObject]) -> str:
    lines: list[str] = []

    for message in messages:
        content = extract_message_content(message)
        if content is None:
            continue

        metadata: list[str] = []
        date = get_optional_str(message, "date")
        if date is not None:
            metadata.append(date)

        sender_id = get_optional_int(message, "sender_id")
        if sender_id is not None:
            metadata.append(f"sender_id={sender_id}")

        prefix = f"[{' | '.join(metadata)}] " if metadata else ""
        lines.append(prefix + content)

    return "\n".join(lines)


def render_prompt(
    template: str,
    key_field: str,
    key_value: object,
    message_count: int,
    transcript: str,
) -> str:
    return template.format(
        group_key_name=key_field,
        group_key_value=stringify_value(key_value),
        message_count=message_count,
        transcript=transcript,
    )


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


def summarize_with_retries(
    prompt: str,
    summarize_fn: SummarizeFn,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_attempts: int = MAX_RETRY_ATTEMPTS,
    base_delay_seconds: float = BASE_RETRY_DELAY_SECONDS,
) -> str:
    attempt = 1

    while True:
        try:
            return summarize_fn(prompt)
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


def build_openrouter_summarizer(model: str, api_key: str, base_url: str) -> SummarizeFn:
    client = OpenAI(api_key=api_key, base_url=base_url)

    def summarize(prompt: str) -> str:
        response = client.responses.create(model=model, input=prompt)
        summary = response.output_text
        if not summary or not summary.strip():
            raise RuntimeError("OpenAI returned an empty summary")
        return summary.strip()

    return summarize


def summarize_rows(args: argparse.Namespace, summarize_fn: SummarizeFn | None = None) -> None:
    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path = make_output_path(input_path, args.output_file)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output paths must be different")

    prompt_path = Path(args.prompt_file)
    prompt_template = prompt_path.read_text(encoding="utf-8")

    input_rows = iter_jsonl(input_path)
    try:
        _, first_row = next(input_rows)
    except StopIteration:
        if args.overwrite or not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("", encoding="utf-8")
            logging.info("Input file is empty, wrote empty output to %s", output_path)
        else:
            logging.info("Input file is empty, existing output left unchanged: %s", output_path)
        return

    key_field = detect_key_field(first_row, args.messages_field, args.key_field)
    processed_keys = set() if args.overwrite else load_processed_keys(output_path, key_field)
    row_summarizer = summarize_fn or build_openrouter_summarizer(args.model, get_api_key(), args.base_url)

    logging.info(
        "Summarizing rows from %s into %s using provider=%s model=%s",
        input_path,
        output_path,
        OUTPUT_PROVIDER,
        args.model,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_mode = "w" if args.overwrite else "a"
    written_rows = 0
    stopped_early = False

    with output_path.open(output_mode, encoding="utf-8") as file:
        for row in chain([first_row], (row for _, row in input_rows)):
            key_value = get_key_value(row, key_field)
            key_token = canonicalize_key(key_value)
            if key_token in processed_keys:
                continue

            messages = get_messages(row, args.messages_field)
            transcript = build_transcript(messages)
            if transcript:
                prompt = render_prompt(prompt_template, key_field, key_value, len(messages), transcript)
                try:
                    summary = summarize_with_retries(prompt, row_summarizer)
                except RetryableLLMError as error:
                    logging.warning(
                        "Stopping early after %s new rows because the provider remains unavailable "
                        "or rate-limited: %s. "
                        "Re-run the same command later to resume from %s=%s.",
                        written_rows,
                        error.cause,
                        key_field,
                        stringify_value(key_value),
                    )
                    stopped_early = True
                    break
            else:
                summary = NO_CONTENT_SUMMARY

            output_row = {
                key_field: key_value,
                "summary": summary,
                "provider": OUTPUT_PROVIDER,
                "model": args.model,
            }
            file.write(json.dumps(output_row, ensure_ascii=False) + "\n")
            processed_keys.add(key_token)
            written_rows += 1

    if stopped_early:
        logging.info("Stopped early. Wrote %s new summary rows before the provider quota/error boundary.", written_rows)
    else:
        logging.info("Done. Wrote %s new summary rows", written_rows)


def main() -> None:
    args = parse_args()
    load_repo_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    summarize_rows(args)


if __name__ == "__main__":
    main()
