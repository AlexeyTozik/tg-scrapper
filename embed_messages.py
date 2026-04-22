import argparse
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import cast

from sentence_transformers import SentenceTransformer

JsonObject = dict[str, object]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read Telegram messages from JSONL and compute embeddings with intfloat/multilingual-e5-small."
    )
    parser.add_argument("--input", default="messages.jsonl", help="Input JSONL file with Telegram messages")
    parser.add_argument("--output", default="message_embeddings.jsonl", help="Output JSONL file with embeddings")
    parser.add_argument(
        "--state",
        default="message_embeddings.state.json",
        help="Checkpoint file for resumable embedding generation",
    )
    parser.add_argument(
        "--model",
        default="intfloat/multilingual-e5-small",
        help="Embedding model name or local path",
    )
    parser.add_argument(
        "--cache-dir",
        default=".cache/sentence-transformers",
        help="Directory where the model will be cached",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="How many messages to embed in one batch",
    )
    parser.add_argument(
        "--device",
        default="cuda",
        help='Device for inference, e.g. "cpu", "cuda", "mps"',
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use only local cached files and do not try to download anything",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=0,
        help="0 = process all messages; otherwise stop after this many embedded messages",
    )
    return parser.parse_args()


def load_state(path: Path) -> JsonObject:
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return cast(JsonObject, raw)

    return {
        "processed_lines": 0,
        "saved_embeddings": 0,
        "skipped_empty": 0,
    }


def save_state(path: Path, state: JsonObject) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, rows: list[JsonObject]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def get_required_int(row: JsonObject, key: str) -> int:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'Field "{key}" is missing or not an int')
    return value


def get_optional_int(row: JsonObject, key: str) -> int | None:
    value = row.get(key)
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def get_optional_str(row: JsonObject, key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) else None


def extract_message_text(row: JsonObject) -> str | None:
    for key in ("text", "raw_text"):
        value = get_optional_str(row, key)
        if value is not None:
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def iter_jsonl(path: Path, skip_lines: int) -> tuple[int, JsonObject] | None:
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if line_number <= skip_lines:
                continue

            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise ValueError(f"Line {line_number} is not a JSON object")

            return line_number, cast(JsonObject, raw)

    return None


def iter_remaining_jsonl(path: Path, skip_lines: int) -> Iterator[tuple[int, JsonObject]]:
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if line_number <= skip_lines:
                continue

            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise ValueError(f"Line {line_number} is not a JSON object")

            yield line_number, cast(JsonObject, raw)


def build_output_rows(
    batch: list[tuple[int, JsonObject, str]],
    vectors: list[list[float]],
    model_name: str,
) -> list[JsonObject]:
    rows: list[JsonObject] = []

    for batch_item, vector in zip(batch, vectors, strict=True):
        _, message, text = batch_item

        rows.append(
            {
                "id": get_required_int(message, "id"),
                "chat_id": get_optional_int(message, "chat_id"),
                "sender_id": get_optional_int(message, "sender_id"),
                "date": get_optional_str(message, "date"),
                "text": text,
                "embedding_model": model_name,
                "embedding_dim": len(vector),
                "embedding": vector,
            }
        )

    return rows


def embed_batch(
    model: SentenceTransformer,
    batch: list[tuple[int, JsonObject, str]],
    batch_size: int,
) -> list[list[float]]:
    passages = [f"passage: {text}" for _, _, text in batch]

    encoded = model.encode(
        passages,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    vectors = cast(list[list[float]], encoded.tolist())
    return vectors


def export_embeddings(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)
    state_path = Path(args.state)
    cache_dir = Path(args.cache_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    cache_dir.mkdir(parents=True, exist_ok=True)

    state = load_state(state_path)

    processed_lines = get_optional_int(state, "processed_lines") or 0
    saved_embeddings = get_optional_int(state, "saved_embeddings") or 0
    skipped_empty = get_optional_int(state, "skipped_empty") or 0

    logging.info("Loading model: %s", args.model)
    model = SentenceTransformer("./models/multilingual-e5-small", local_files_only=True, device=args.device)

    batch: list[tuple[int, JsonObject, str]] = []

    for line_number, row in iter_remaining_jsonl(input_path, processed_lines):
        text = extract_message_text(row)

        if text is None:
            processed_lines = line_number
            skipped_empty += 1
            continue

        batch.append((line_number, row, text))

        if len(batch) < args.batch_size:
            continue

        vectors = embed_batch(model, batch, args.batch_size)
        output_rows = build_output_rows(batch, vectors, args.model)
        append_jsonl(output_path, output_rows)

        processed_lines = batch[-1][0]
        saved_embeddings += len(output_rows)

        state = {
            "processed_lines": processed_lines,
            "saved_embeddings": saved_embeddings,
            "skipped_empty": skipped_empty,
        }
        save_state(state_path, state)

        logging.info(
            "Saved batch: %s embeddings | processed lines: %s | total saved: %s | skipped empty: %s",
            len(output_rows),
            processed_lines,
            saved_embeddings,
            skipped_empty,
        )

        batch.clear()

        if args.max_messages > 0 and saved_embeddings >= args.max_messages:
            logging.info("Reached max-messages=%s", args.max_messages)
            return

    if batch:
        vectors = embed_batch(model, batch, args.batch_size)
        output_rows = build_output_rows(batch, vectors, args.model)
        append_jsonl(output_path, output_rows)

        processed_lines = batch[-1][0]
        saved_embeddings += len(output_rows)

        state = {
            "processed_lines": processed_lines,
            "saved_embeddings": saved_embeddings,
            "skipped_empty": skipped_empty,
        }
        save_state(state_path, state)

        logging.info(
            "Saved final batch: %s embeddings | processed lines: %s | total saved: %s | skipped empty: %s",
            len(output_rows),
            processed_lines,
            saved_embeddings,
            skipped_empty,
        )

    logging.info("Done. Total saved embeddings: %s | skipped empty messages: %s", saved_embeddings, skipped_empty)


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    export_embeddings(args)


if __name__ == "__main__":
    main()
