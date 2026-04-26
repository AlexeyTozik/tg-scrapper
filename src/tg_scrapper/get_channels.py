import argparse
import asyncio
from collections.abc import Sequence

from telethon import TelegramClient

from .app_support import get_first_env, load_repo_dotenv


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List available Telegram channels and chats from the current session.")
    parser.add_argument("--session", default="session_name", help="Telethon session name/path")
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> None:
    load_repo_dotenv()

    api_id = get_first_env("TG_API_ID")
    api_hash = get_first_env("TG_API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError("Set TG_API_ID and TG_API_HASH environment variables")

    client = TelegramClient(args.session, int(api_id), api_hash)
    async with client:
        await client.start()
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if getattr(entity, "broadcast", False) or getattr(entity, "megagroup", False):
                peer_id = await client.get_peer_id(entity)
                print(f"{dialog.name} | entity.id={entity.id} | peer_id={peer_id}")


def cli_main(argv: Sequence[str] | None = None) -> None:
    asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    cli_main()
