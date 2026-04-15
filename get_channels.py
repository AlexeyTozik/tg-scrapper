import os

from telethon import TelegramClient

api_id = os.getenv("TG_API_ID")
api_hash = os.getenv("TG_API_HASH")

client = TelegramClient("session_name", int(api_id), api_hash)  # type: ignore[arg-type]


async def main() -> None:
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if getattr(entity, "broadcast", False) or getattr(entity, "megagroup", False):
            peer_id = await client.get_peer_id(entity)
            print(f"{dialog.name} | entity.id={entity.id} | peer_id={peer_id}")


with client:
    client.loop.run_until_complete(main())
