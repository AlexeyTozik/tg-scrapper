import argparse
import importlib
import sys
from collections.abc import Sequence
from typing import Protocol, cast


class CLIEntrypoint(Protocol):
    def __call__(self, argv: Sequence[str] | None = None) -> None: ...


COMMANDS: dict[str, tuple[str, str]] = {
    "channels": ("List Telegram channels visible in the current session", "tg_scrapper.get_channels"),
    "export": ("Export Telegram messages to JSONL", "tg_scrapper.export_messages"),
    "embed": ("Compute embeddings for exported messages", "tg_scrapper.embed_messages"),
    "index": ("Index embeddings into ChromaDB", "tg_scrapper.index_messages"),
    "query": ("Query the ChromaDB index with RAG", "tg_scrapper.rag_query"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tg-scrapper",
        description="Telegram export, embeddings, indexing, and RAG query CLI.",
    )
    parser.add_argument("command", nargs="?", help="Subcommand to run")
    return parser


def format_commands_help() -> str:
    lines = ["Available commands:"]
    for name, (description, _) in COMMANDS.items():
        lines.append(f"  {name:<8} {description}")
    return "\n".join(lines)


def resolve_entrypoint(command: str) -> CLIEntrypoint:
    if command not in COMMANDS:
        raise KeyError(command)

    _, module_name = COMMANDS[command]
    module = importlib.import_module(module_name)
    entrypoint = cast(CLIEntrypoint, module.cli_main)
    return entrypoint


def main(argv: Sequence[str] | None = None) -> None:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()

    if not args_list:
        parser.print_help()
        print()
        print(format_commands_help())
        return

    if args_list[0] in {"-h", "--help"}:
        parser.print_help()
        print()
        print(format_commands_help())
        return

    command = args_list[0]
    if command not in COMMANDS:
        parser.error(f"unknown command: {command}")

    resolve_entrypoint(command)(args_list[1:])
