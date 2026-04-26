import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from sentence_transformers import SentenceTransformer

from .app_support import load_repo_dotenv
from .chroma_store import MESSAGES_COLLECTION, QueryHit, get_messages_collection, query_items
from .llm_client import (
    DEFAULT_OPENROUTER_BASE_URL,
    build_openrouter_client,
    call_with_retries,
    get_api_key,
)
from .query_expansion import expand_query
from .resources import read_prompt_text
from .retrieval import build_where_filter, format_context, merge_hits, mmr_rerank

DEFAULT_ANSWERS_DIR = Path("answers")


@dataclass(frozen=True)
class QueryConfig:
    question: str
    chroma_path: Path
    collection: str
    model: str
    cache_dir: Path
    device: str
    offline: bool
    llm_model: str
    base_url: str
    top_k_per_query: int
    final_k: int
    num_variants: int
    mmr_lambda: float
    since: str | None
    until: str | None
    channels: str | None
    chat_ids: str | None
    with_links_only: bool
    min_chars: int
    prompt_multi_query: str | None
    prompt_answer: str | None
    output: Path | None
    output_dir: Path
    no_expand: bool
    debug: bool

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "QueryConfig":
        return cls(
            question=args.question,
            chroma_path=Path(args.chroma_path),
            collection=args.collection,
            model=args.model,
            cache_dir=Path(args.cache_dir),
            device=args.device,
            offline=args.offline,
            llm_model=args.llm_model,
            base_url=args.base_url,
            top_k_per_query=args.top_k_per_query,
            final_k=args.final_k,
            num_variants=args.num_variants,
            mmr_lambda=args.mmr_lambda,
            since=args.since,
            until=args.until,
            channels=args.channels,
            chat_ids=args.chat_ids,
            with_links_only=args.with_links_only,
            min_chars=args.min_chars,
            prompt_multi_query=args.prompt_multi_query,
            prompt_answer=args.prompt_answer,
            output=Path(args.output) if args.output else None,
            output_dir=Path(args.output_dir),
            no_expand=args.no_expand,
            debug=args.debug,
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Topic-focused RAG query over the Telegram messages collection in ChromaDB."
    )
    parser.add_argument("--question", required=True, help="User question in any language")
    parser.add_argument("--chroma-path", default="./chroma_db", help="ChromaDB persistent directory")
    parser.add_argument("--collection", default=MESSAGES_COLLECTION, help="ChromaDB collection name")
    parser.add_argument(
        "--model",
        default="./models/multilingual-e5-small",
        help="Embedding model name or local path",
    )
    parser.add_argument(
        "--cache-dir",
        default=".cache/sentence-transformers",
        help="Directory where the embedding model is cached",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "mps", "cuda"],
        help="Device for embedding the query; auto picks cuda > mps > cpu",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use only local embedding model files",
    )
    parser.add_argument(
        "--llm-model",
        default="openai/gpt-oss-120b:free",
        help="OpenRouter model id for multi-query expansion and answer synthesis",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_OPENROUTER_BASE_URL,
        help="OpenRouter-compatible base URL",
    )
    parser.add_argument("--top-k-per-query", type=int, default=100, help="Top-K hits per query variant")
    parser.add_argument("--final-k", type=int, default=20, help="Number of messages in final context after MMR")
    parser.add_argument("--num-variants", type=int, default=4, help="Number of query paraphrases to generate")
    parser.add_argument("--mmr-lambda", type=float, default=0.5, help="MMR relevance/diversity trade-off")
    parser.add_argument("--since", help="ISO date lower bound (YYYY-MM-DD)")
    parser.add_argument("--until", help="ISO date upper bound (YYYY-MM-DD)")
    parser.add_argument(
        "--channels",
        help="Comma-separated list of channel_name values to include",
    )
    parser.add_argument(
        "--chat-ids",
        help="Comma-separated list of chat_id integers to include",
    )
    parser.add_argument("--with-links-only", action="store_true", help="Keep only messages with URLs")
    parser.add_argument("--min-chars", type=int, default=20, help="Minimum text_length to include")
    parser.add_argument(
        "--prompt-multi-query",
        help="Optional path to the multi-query expansion prompt template",
    )
    parser.add_argument(
        "--prompt-answer",
        help="Optional path to the final answer synthesis prompt template",
    )
    parser.add_argument(
        "--output",
        help="Write answer to this file instead of the default answers/<timestamp>.md",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_ANSWERS_DIR),
        help="Directory for default answer files",
    )
    parser.add_argument(
        "--no-expand",
        action="store_true",
        help="Skip multi-query expansion and use the raw question only",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print final hits (text, distance, channel, date) before generating the answer",
    )
    return parser.parse_args(argv)


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested

    import torch

    if torch.cuda.is_available():
        return "cuda"

    mps_backend = getattr(torch.backends, "mps", None)
    if mps_backend is not None and bool(mps_backend.is_available()):
        return "mps"

    return "cpu"


def embed_query(model: SentenceTransformer, text: str) -> list[float]:
    encoded = model.encode(
        [f"query: {text}"],
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return cast(list[list[float]], encoded.tolist())[0]


def timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%d-%m-%Y-%H-%M-%S")


def resolve_output_path(config: QueryConfig) -> Path:
    if config.output:
        return config.output
    directory = config.output_dir
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{timestamp_slug()}.md"


def run(config: QueryConfig) -> None:
    load_repo_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    device = resolve_device(config.device)
    logging.info("Embedding device: %s", device)

    cache_dir = config.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    logging.info("Loading embedding model: %s", config.model)
    model = SentenceTransformer(
        config.model,
        cache_folder=str(cache_dir),
        local_files_only=config.offline,
        device=device,
    )

    collection = get_messages_collection(config.chroma_path, name=config.collection)
    logging.info("Collection '%s' count: %s", config.collection, collection.count())

    llm = build_openrouter_client(config.llm_model, get_api_key(), config.base_url)

    if config.no_expand or config.num_variants <= 1:
        variants = [config.question]
    else:
        variants = expand_query(
            question=config.question,
            num_variants=config.num_variants,
            prompt_path=config.prompt_multi_query,
            llm=llm,
        )

    logging.info("Query variants: %s", variants)

    where = build_where_filter(config)
    logging.info("Where filter: %s", where)

    hit_lists: list[list[QueryHit]] = []
    for variant in variants:
        vector = embed_query(model, variant)
        hits = query_items(
            collection=collection,
            vector=vector,
            top_k=config.top_k_per_query,
            where=where,
            include_embeddings=True,
        )
        logging.info("Variant '%s' -> %s hits", variant[:60], len(hits))
        hit_lists.append(hits)

    merged = merge_hits(hit_lists)
    logging.info("Merged unique hits: %s", len(merged))

    final_hits = mmr_rerank(merged, config.final_k, config.mmr_lambda)
    logging.info("Final hits after MMR: %s", len(final_hits))

    if config.debug:
        print("\n=== DEBUG: final hits ===")
        for index, hit in enumerate(final_hits, start=1):
            metadata = hit.metadata
            channel = metadata.get("channel_name", "?")
            message_id = metadata.get("id", "?")
            date = metadata.get("date", "?")
            print(f"\n[#{index}] distance={hit.distance:.4f} channel={channel} msg_id={message_id} date={date}")
            print(hit.document[:500])
        print("\n=== END DEBUG ===\n")

    if not final_hits:
        answer = "Не нашёл релевантных сообщений под фильтры запроса."  # noqa: RUF001
    else:
        prompt_template = read_prompt_text(config.prompt_answer, default_filename="rag_answer.txt")
        prompt = prompt_template.format(
            question=config.question,
            context=format_context(final_hits),
        )
        answer = call_with_retries(prompt, llm)

    output_path = resolve_output_path(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(answer.rstrip() + "\n", encoding="utf-8")

    print(answer)
    logging.info("Answer written to %s", output_path)


def cli_main(argv: Sequence[str] | None = None) -> None:
    run(QueryConfig.from_args(parse_args(argv)))


if __name__ == "__main__":
    cli_main()
