import argparse
from pathlib import Path

from app_support import JsonObject, get_optional_int, get_required_int, read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Group Telegram messages from JSONL into thread-based JSONL output.")
    parser.add_argument("--input", default="messages.jsonl", help="Input JSONL file with Telegram messages")
    parser.add_argument("--output", default="threads.jsonl", help="Output JSONL file with grouped threads")
    return parser.parse_args()


def resolve_thread_id(
    message_id: int,
    messages_by_id: dict[int, JsonObject],
    resolved_roots: dict[int, int],
) -> int:
    if message_id in resolved_roots:
        return resolved_roots[message_id]

    seen_ids: list[int] = []
    current_id = message_id

    while True:
        cached_root = resolved_roots.get(current_id)
        if cached_root is not None:
            root_id = cached_root
            break

        if current_id in seen_ids:
            root_id = current_id
            break

        seen_ids.append(current_id)

        current_message = messages_by_id.get(current_id)
        if current_message is None:
            root_id = current_id
            break

        parent_id = get_optional_int(current_message, "reply_to_msg_id")
        if parent_id is None:
            root_id = current_id
            break

        if parent_id not in messages_by_id:
            root_id = parent_id
            break

        current_id = parent_id

    for seen_id in seen_ids:
        resolved_roots[seen_id] = root_id

    return root_id


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    message_items: list[tuple[int, JsonObject]] = []
    messages_by_id: dict[int, JsonObject] = {}

    for message in read_jsonl(input_path):
        message_id = get_required_int(message, "id")
        if message_id in messages_by_id:
            raise ValueError(f"Duplicate message id: {message_id}")
        messages_by_id[message_id] = message
        message_items.append((message_id, message))

    resolved_roots: dict[int, int] = {}
    grouped_threads: dict[int, list[JsonObject]] = {}

    for message_id, message in message_items:
        thread_id = resolve_thread_id(message_id, messages_by_id, resolved_roots)
        grouped_threads.setdefault(thread_id, []).append(message)

    rows: list[JsonObject] = [
        {
            "thread_id": thread_id,
            "messages": thread_messages,
        }
        for thread_id, thread_messages in grouped_threads.items()
    ]

    write_jsonl(output_path, rows)


if __name__ == "__main__":
    main()
