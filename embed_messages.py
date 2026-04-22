import argparse
import logging
from pathlib import Path
from typing import cast

from sentence_transformers import SentenceTransformer

from app_support import (
    JsonObject,
    append_jsonl,
    get_optional_int,
    get_optional_str,
    get_required_int,
    iter_jsonl,
    load_json_dict,
    save_json,
)


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
    state = load_json_dict(path)
    if state is not None:
        return cast(JsonObject, state)

    return {
        "processed_lines": 0,
        "saved_embeddings": 0,
        "skipped_empty": 0,
    }


def save_state(path: Path, state: JsonObject) -> None:
    save_json(path, state, indent=2)


def extract_message_text(row: JsonObject) -> str | None:
    for key in ("text", "raw_text"):
        value = get_optional_str(row, key)
        if value is not None:
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


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


def get_target_batch_size(batch_size: int, max_messages: int, saved_embeddings: int) -> int:
    if max_messages <= 0:
        return batch_size

    remaining = max_messages - saved_embeddings
    if remaining <= 0:
        return 0

    return min(batch_size, remaining)


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
    model = SentenceTransformer(
        args.model,
        cache_folder=str(cache_dir),
        local_files_only=args.offline,
        device=args.device,
    )

    batch: list[tuple[int, JsonObject, str]] = []

    for line_number, row in iter_jsonl(input_path, processed_lines):
        target_batch_size = get_target_batch_size(args.batch_size, args.max_messages, saved_embeddings)
        if target_batch_size == 0:
            logging.info("Reached max-messages=%s", args.max_messages)
            return

        text = extract_message_text(row)

        if text is None:
            processed_lines = line_number
            skipped_empty += 1
            continue

        batch.append((line_number, row, text))

        if len(batch) < target_batch_size:
            continue

        vectors = embed_batch(model, batch, target_batch_size)
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
        target_batch_size = get_target_batch_size(args.batch_size, args.max_messages, saved_embeddings)
        if target_batch_size == 0:
            logging.info("Reached max-messages=%s", args.max_messages)
            return

        final_batch = batch[:target_batch_size]
        vectors = embed_batch(model, final_batch, target_batch_size)
        output_rows = build_output_rows(final_batch, vectors, args.model)
        append_jsonl(output_path, output_rows)

        processed_lines = final_batch[-1][0]
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
