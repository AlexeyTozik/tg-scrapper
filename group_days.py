import argparse
from pathlib import Path

from app_support import JsonObject, get_required_str, iter_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Group Telegram messages from JSONL into day-based JSONL output.")
    parser.add_argument("--input", default="messages.jsonl", help="Input JSONL file with Telegram messages")
    parser.add_argument("--output", default="days.jsonl", help="Output JSONL file with grouped days")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    grouped_days: dict[str, list[JsonObject]] = {}

    for _, message in iter_jsonl(input_path):
        day = get_required_str(message, "date").split("T", 1)[0]
        grouped_days.setdefault(day, []).append(message)

    rows: list[JsonObject] = [
        {
            "day": day,
            "messages": day_messages,
        }
        for day, day_messages in grouped_days.items()
    ]

    write_jsonl(output_path, rows)


if __name__ == "__main__":
    main()
