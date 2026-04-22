import argparse
import asyncio

from telethon import TelegramClient

from app_support import get_first_env, load_repo_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List available Telegram channels and chats from the current session.")
    parser.add_argument("--session", default="session_name", help="Telethon session name/path")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
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


if __name__ == "__main__":
    asyncio.run(main())
