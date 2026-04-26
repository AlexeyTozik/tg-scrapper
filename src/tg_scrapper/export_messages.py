import argparse
import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from telethon import TelegramClient, errors
from telethon.tl.types import PeerChannel

from .app_support import append_jsonl, get_first_env, load_repo_dotenv
from .checkpoints import load_checkpoint, save_checkpoint
from .telegram_export import serialize_message

DEFAULT_BATCH_SIZE = 1000
DEFAULT_HISTORY_WAIT = 0.0
DEFAULT_BATCH_SLEEP = 0.0


@dataclass(frozen=True)
class ExportRuntimeOptions:
    batch_size: int
    history_wait: float
    batch_sleep: float
    use_takeout: bool


@dataclass(frozen=True)
class ExportConfig:
    channel: str
    session: str
    out: Path
    state: Path
    batch_size: int
    history_wait: float
    batch_sleep: float
    max_messages: int

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "ExportConfig":
        return cls(
            channel=args.channel,
            session=args.session,
            out=Path(args.out),
            state=Path(args.state),
            batch_size=args.batch_size,
            history_wait=args.history_wait,
            batch_sleep=args.batch_sleep,
            max_messages=args.max_messages,
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch export messages from a Telegram channel using Telethon.")
    parser.add_argument("--channel", required=True, help="Username, invite link or numeric id")
    parser.add_argument("--session", default="tg_session", help="Telethon session name/path")
    parser.add_argument("--out", default="messages.jsonl", help="Output JSONL file")
    parser.add_argument("--state", default="messages.state.json", help="Checkpoint file")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Messages per app batch")
    parser.add_argument(
        "--history-wait",
        type=float,
        default=DEFAULT_HISTORY_WAIT,
        help="Pause between Telethon history requests (seconds)",
    )
    parser.add_argument(
        "--batch-sleep",
        type=float,
        default=DEFAULT_BATCH_SLEEP,
        help="Pause after each saved batch (seconds)",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=0,
        help="0 = export all; otherwise stop after this many messages",
    )
    return parser.parse_args(argv)


def resolve_runtime_options(config: ExportConfig) -> ExportRuntimeOptions:
    return ExportRuntimeOptions(
        batch_size=config.batch_size,
        history_wait=config.history_wait,
        batch_sleep=config.batch_sleep,
        use_takeout=True,
    )


def build_iter_messages_kwargs(
    entity: str | PeerChannel | Any,
    *,
    limit_left: int | None,
    min_id: int,
    history_wait: float,
) -> dict[str, object]:
    return {
        "entity": entity,
        "limit": limit_left,
        "reverse": True,
        "min_id": min_id,
        "wait_time": history_wait,
    }


async def iter_history_messages(
    client: TelegramClient,
    entity: str | PeerChannel | Any,
    *,
    limit_left: int | None,
    min_id: int,
    runtime: ExportRuntimeOptions,
) -> AsyncIterator[Any]:
    iter_kwargs = build_iter_messages_kwargs(
        entity,
        limit_left=limit_left,
        min_id=min_id,
        history_wait=runtime.history_wait,
    )

    if runtime.use_takeout:
        try:
            async with client.takeout(channels=True, megagroups=True) as takeout:
                async for msg in takeout.iter_messages(**iter_kwargs):
                    yield msg
            return
        except errors.TakeoutInitDelayError as exc:
            logging.warning(
                "Takeout export is not ready yet (wait %s seconds). Falling back to the normal client.",
                exc.seconds,
            )
        except ValueError as exc:
            if "takeout" not in str(exc).lower():
                raise
            logging.warning("Takeout export is already pending. Falling back to the normal client.")

    async for msg in client.iter_messages(**iter_kwargs):
        yield msg


def load_export_state(path: Path) -> dict[str, Any]:
    return load_checkpoint(path, {"last_id": 0, "saved_messages": 0, "updated_at": None})


def save_export_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(UTC).isoformat()
    save_checkpoint(path, state)


def parse_channel_ref(channel: str) -> str | PeerChannel:
    if channel.startswith("-100") and channel[4:].isdigit():
        return PeerChannel(int(channel[4:]))

    if channel.isdigit():
        return PeerChannel(int(channel))

    return channel


async def resolve_entity(client: TelegramClient, channel: str) -> str | PeerChannel | Any:
    channel_ref = parse_channel_ref(channel)

    try:
        return await client.get_input_entity(channel_ref)
    except ValueError:
        if isinstance(channel_ref, PeerChannel):
            # Numeric peer IDs require the entity cache to be populated first.
            await client.get_dialogs()
            return await client.get_input_entity(channel_ref)
        raise


async def flush_batch(
    batch: list[Any],
    out_path: Path,
    state_path: Path,
    state: dict[str, Any],
    channel_name: str | None,
) -> None:
    if not batch:
        return

    rows = [serialize_message(m, channel_name) for m in batch if m]
    append_jsonl(out_path, rows)

    state["last_id"] = batch[-1].id
    state["saved_messages"] += len(rows)
    save_export_state(state_path, state)

    logging.info(
        "Saved batch: %s messages | ids %s..%s | total saved: %s",
        len(rows),
        batch[0].id,
        batch[-1].id,
        state["saved_messages"],
    )


async def export_messages(client: TelegramClient, config: ExportConfig) -> None:
    runtime = resolve_runtime_options(config)
    out_path = config.out
    state_path = config.state
    state = load_export_state(state_path)

    entity = await resolve_entity(client, config.channel)
    full_entity = await client.get_entity(entity)
    channel_name = getattr(full_entity, "title", None) or getattr(full_entity, "username", None)
    logging.info("Resolved entity: %s", channel_name)
    logging.info(
        "Export runtime: takeout=%s batch_size=%s history_wait=%s batch_sleep=%s",
        runtime.use_takeout,
        runtime.batch_size,
        runtime.history_wait,
        runtime.batch_sleep,
    )

    batch: list[Any] = []
    limit_left = config.max_messages if config.max_messages > 0 else None

    while True:
        try:
            async for msg in iter_history_messages(
                client,
                entity,
                limit_left=limit_left,
                min_id=state["last_id"],
                runtime=runtime,
            ):
                if not msg:
                    continue

                batch.append(msg)

                if len(batch) >= runtime.batch_size:
                    await flush_batch(batch, out_path, state_path, state, channel_name)
                    batch.clear()

                    if config.max_messages > 0:
                        limit_left = max(0, config.max_messages - state["saved_messages"])
                        if limit_left == 0:
                            logging.info("Reached max-messages=%s", config.max_messages)
                            return

                    if runtime.batch_sleep > 0:
                        await asyncio.sleep(runtime.batch_sleep)

            # normal end of iteration
            if batch:
                await flush_batch(batch, out_path, state_path, state, channel_name)
                batch.clear()

            break

        except errors.FloodWaitError as e:
            # flush what we already accumulated so we do not lose progress
            if batch:
                await flush_batch(batch, out_path, state_path, state, channel_name)
                batch.clear()

            sleep_for = int(e.seconds) + 1
            logging.warning("FloodWaitError: sleeping for %s seconds", sleep_for)
            await asyncio.sleep(sleep_for)

    logging.info("Done. Total saved: %s", state["saved_messages"])


async def run(config: ExportConfig) -> None:
    load_repo_dotenv()

    api_id = get_first_env("TG_API_ID")
    api_hash = get_first_env("TG_API_HASH")

    if not api_id or not api_hash:
        raise RuntimeError("Set TG_API_ID and TG_API_HASH environment variables")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    client = TelegramClient(config.session, int(api_id), api_hash)

    async with client:
        # first run will ask for phone/code/2FA if needed
        await client.start()
        await export_messages(client, config)


def cli_main(argv: Sequence[str] | None = None) -> None:
    asyncio.run(run(ExportConfig.from_args(parse_args(argv))))


if __name__ == "__main__":
    cli_main()
