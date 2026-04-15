import argparse
import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from telethon import TelegramClient, errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch export messages from a Telegram channel using Telethon.")
    parser.add_argument("--channel", required=True, help="Username, invite link or numeric id")
    parser.add_argument("--session", default="tg_session", help="Telethon session name/path")
    parser.add_argument("--out", default="messages.jsonl", help="Output JSONL file")
    parser.add_argument("--state", default="messages.state.json", help="Checkpoint file")
    parser.add_argument("--batch-size", type=int, default=200, help="Messages per app batch")
    parser.add_argument(
        "--history-wait",
        type=float,
        default=1.5,
        help="Pause between Telethon history requests (seconds)",
    )
    parser.add_argument(
        "--batch-sleep",
        type=float,
        default=2.0,
        help="Pause after each saved batch (seconds)",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=0,
        help="0 = export all; otherwise stop after this many messages",
    )
    return parser.parse_args()


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    return {
        "last_id": 0,
        "saved_messages": 0,
        "updated_at": None,
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def serialize_message(msg: Any) -> dict[str, Any]:
    return {
        "id": msg.id,
        "date": msg.date.isoformat() if msg.date else None,
        "text": msg.message,
        "raw_text": msg.raw_text,
        "sender_id": msg.sender_id,
        "chat_id": msg.chat_id,
        "views": getattr(msg, "views", None),
        "forwards": getattr(msg, "forwards", None),
        "replies": getattr(getattr(msg, "replies", None), "replies", None),
        "reply_to_msg_id": getattr(getattr(msg, "reply_to", None), "reply_to_msg_id", None),
        "post_author": getattr(msg, "post_author", None),
        "grouped_id": getattr(msg, "grouped_id", None),
        "has_media": msg.media is not None,
    }


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


async def flush_batch(
    batch: list[Any],
    out_path: Path,
    state_path: Path,
    state: dict[str, Any],
) -> None:
    if not batch:
        return

    rows = [serialize_message(m) for m in batch if m]
    append_jsonl(out_path, rows)

    state["last_id"] = batch[-1].id
    state["saved_messages"] += len(rows)
    save_state(state_path, state)

    logging.info(
        "Saved batch: %s messages | ids %s..%s | total saved: %s",
        len(rows),
        batch[0].id,
        batch[-1].id,
        state["saved_messages"],
    )


async def export_messages(client: TelegramClient, args: argparse.Namespace) -> None:
    out_path = Path(args.out)
    state_path = Path(args.state)
    state = load_state(state_path)

    entity = await client.get_entity(args.channel)
    logging.info("Resolved entity: %s", getattr(entity, "title", None) or getattr(entity, "username", None))

    batch: list[Any] = []
    limit_left = args.max_messages if args.max_messages > 0 else None

    while True:
        try:
            async for msg in client.iter_messages(
                entity,
                limit=limit_left,
                reverse=True,  # oldest -> newest
                min_id=state["last_id"],  # continue after checkpoint
                wait_time=args.history_wait,
            ):
                if not msg:
                    continue

                batch.append(msg)

                if len(batch) >= args.batch_size:
                    await flush_batch(batch, out_path, state_path, state)
                    batch.clear()

                    if args.max_messages > 0:
                        limit_left = max(0, args.max_messages - state["saved_messages"])
                        if limit_left == 0:
                            logging.info("Reached max-messages=%s", args.max_messages)
                            return

                    await asyncio.sleep(args.batch_sleep)

            # normal end of iteration
            if batch:
                await flush_batch(batch, out_path, state_path, state)
                batch.clear()

            break

        except errors.FloodWaitError as e:
            # flush what we already accumulated so we do not lose progress
            if batch:
                await flush_batch(batch, out_path, state_path, state)
                batch.clear()

            sleep_for = int(e.seconds) + 1
            logging.warning("FloodWaitError: sleeping for %s seconds", sleep_for)
            await asyncio.sleep(sleep_for)

    logging.info("Done. Total saved: %s", state["saved_messages"])


async def main() -> None:
    args = parse_args()

    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")

    if not api_id or not api_hash:
        raise RuntimeError("Set TG_API_ID and TG_API_HASH environment variables")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    client = TelegramClient(args.session, int(api_id), api_hash)

    async with client:
        # first run will ask for phone/code/2FA if needed
        await client.start()
        await export_messages(client, args)


if __name__ == "__main__":
    asyncio.run(main())
