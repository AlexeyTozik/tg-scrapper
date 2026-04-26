import argparse
import glob as glob_module
import logging
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .app_support import (
    JsonObject,
    get_optional_int,
    get_optional_str,
    get_required_int,
    iter_jsonl,
)
from .checkpoints import load_checkpoint, save_checkpoint
from .chroma_store import (
    MESSAGES_COLLECTION,
    MessageMetadata,
    StoreItem,
    get_messages_collection,
    upsert_items,
)
from .message_filter import extract_message_text, get_filtered_message_text

LINK_RE = re.compile(r"https?://", flags=re.IGNORECASE)


@dataclass(frozen=True)
class IndexConfig:
    input: str
    chroma_path: Path
    collection: str
    state: Path
    batch_size: int
    min_chars: int
    max_items: int

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "IndexConfig":
        return cls(
            input=args.input,
            chroma_path=Path(args.chroma_path),
            collection=args.collection,
            state=Path(args.state),
            batch_size=args.batch_size,
            min_chars=args.min_chars,
            max_items=args.max_items,
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stream message_embeddings.jsonl files into the ChromaDB "
            "messages collection without recomputing embeddings."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input file path or glob pattern (e.g. 'exports/*.embeddings.jsonl')",
    )
    parser.add_argument(
        "--chroma-path",
        default="./chroma_db",
        help="Directory for the persistent ChromaDB store",
    )
    parser.add_argument(
        "--collection",
        default=MESSAGES_COLLECTION,
        help="ChromaDB collection name",
    )
    parser.add_argument(
        "--state",
        default="message_embeddings.index.state.json",
        help="State file tracking processed line count per input file",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="How many messages to upsert in one Chroma call",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=20,
        help="Keep short messages only when they match reply/technical heuristics",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="0 = all; otherwise stop after this many indexed messages across all inputs",
    )
    return parser.parse_args(argv)


def expand_inputs(pattern: str) -> list[Path]:
    direct = Path(pattern)
    if direct.is_file():
        return [direct]
    matches = sorted(Path(match) for match in glob_module.glob(pattern))
    return [path for path in matches if path.is_file()]


def load_index_state(path: Path) -> dict[str, int]:
    raw = load_checkpoint(path, {"processed_files": {}})
    processed = raw.get("processed_files")
    if not isinstance(processed, dict):
        return {}
    result: dict[str, int] = {}
    for key, value in processed.items():
        if isinstance(key, str) and isinstance(value, int):
            result[key] = value
    return result


def save_index_state(path: Path, processed_files: dict[str, int]) -> None:
    save_checkpoint(path, {"processed_files": processed_files})


def extract_date(row: JsonObject) -> str | None:
    raw = get_optional_str(row, "date")
    if raw is None:
        return None
    return raw.split("T", 1)[0]


def date_to_int(date: str) -> int | None:
    try:
        return int(date.replace("-", ""))
    except ValueError:
        return None


def build_metadata(row: JsonObject) -> MessageMetadata:
    text = extract_message_text(row) or ""
    metadata: MessageMetadata = {
        "id": get_required_int(row, "id"),
        "text_length": len(text),
        "has_link": bool(LINK_RE.search(text)),
    }
    chat_id = get_optional_int(row, "chat_id")
    if chat_id is not None:
        metadata["chat_id"] = chat_id
    channel_name = get_optional_str(row, "channel_name")
    if channel_name is not None:
        metadata["channel_name"] = channel_name
    sender_id = get_optional_int(row, "sender_id")
    if sender_id is not None:
        metadata["sender_id"] = sender_id
    date = extract_date(row)
    if date is not None:
        metadata["date"] = date
        date_int = date_to_int(date)
        if date_int is not None:
            metadata["date_int"] = date_int
    return metadata


def build_item(row: JsonObject, min_chars: int) -> StoreItem | None:
    text = get_filtered_message_text(row, min_chars=min_chars)
    if text is None:
        return None

    raw_embedding = row.get("embedding")
    if not isinstance(raw_embedding, list):
        return None
    embedding = cast(list[float], raw_embedding)

    chat_id = get_optional_int(row, "chat_id")
    message_id = get_required_int(row, "id")
    chat_token = str(chat_id) if chat_id is not None else "unknown"

    return StoreItem(
        id=f"msg:{chat_token}:{message_id}",
        document=text,
        embedding=embedding,
        metadata=build_metadata(row),
    )


def index_file(
    path: Path,
    collection: object,
    *,
    start_line: int,
    batch_size: int,
    min_chars: int,
    indexed_total: int,
    budget: int | None,
) -> tuple[int, int, int]:
    from chromadb.api.models.Collection import Collection

    typed_collection = cast(Collection, collection)

    buffer: list[StoreItem] = []
    last_line = start_line
    indexed_here = 0
    skipped_here = 0

    def flush() -> int:
        if not buffer:
            return 0
        written = upsert_items(typed_collection, buffer)
        buffer.clear()
        return written

    started_at = time.monotonic()

    for line_number, row in iter_jsonl(path, skip_lines=start_line):
        last_line = line_number
        item = build_item(row, min_chars)
        if item is None:
            skipped_here += 1
            continue

        buffer.append(item)

        if len(buffer) >= batch_size:
            written = flush()
            indexed_here += written
            rate = indexed_here / max(time.monotonic() - started_at, 1e-6)
            logging.info(
                "%s: line=%s indexed=%s skipped=%s (~%.0f msg/s)",
                path.name,
                last_line,
                indexed_here,
                skipped_here,
                rate,
            )
            if budget is not None and indexed_total + indexed_here >= budget:
                return last_line, indexed_here, skipped_here

    written = flush()
    indexed_here += written

    return last_line, indexed_here, skipped_here


def run(config: IndexConfig) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    inputs = expand_inputs(config.input)
    if not inputs:
        raise FileNotFoundError(f"No input files match: {config.input}")

    logging.info("Inputs: %s", [str(p) for p in inputs])

    state_path = config.state
    processed_files = load_index_state(state_path)

    collection = get_messages_collection(config.chroma_path, name=config.collection)
    logging.info("Collection '%s' starting count: %s", config.collection, collection.count())

    budget: int | None = config.max_items if config.max_items > 0 else None
    indexed_total = 0
    skipped_total = 0

    for path in inputs:
        key = str(path)
        start_line = processed_files.get(key, 0)
        logging.info("Indexing %s starting from line %s", path, start_line)

        last_line, indexed_here, skipped_here = index_file(
            path=path,
            collection=collection,
            start_line=start_line,
            batch_size=config.batch_size,
            min_chars=config.min_chars,
            indexed_total=indexed_total,
            budget=budget,
        )

        indexed_total += indexed_here
        skipped_total += skipped_here
        processed_files[key] = last_line
        save_index_state(state_path, processed_files)

        logging.info(
            "Finished %s: indexed=%s skipped=%s last_line=%s",
            path.name,
            indexed_here,
            skipped_here,
            last_line,
        )

        if budget is not None and indexed_total >= budget:
            logging.info("Reached --max-items=%s", config.max_items)
            break

    logging.info(
        "Done. Total indexed=%s skipped=%s | collection count=%s",
        indexed_total,
        skipped_total,
        collection.count(),
    )


def cli_main(argv: Sequence[str] | None = None) -> None:
    run(IndexConfig.from_args(parse_args(argv)))


if __name__ == "__main__":
    cli_main()
