# ruff: noqa: RUF001

import argparse
import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sentence_transformers import SentenceTransformer

from app_support import load_repo_dotenv
from chroma_store import MESSAGES_COLLECTION, QueryHit, get_messages_collection, query_items
from llm_client import (
    DEFAULT_OPENROUTER_BASE_URL,
    build_openrouter_client,
    call_with_retries,
    get_api_key,
)

DEFAULT_ANSWERS_DIR = Path("answers")
CODE_FENCE_OPEN_RE = re.compile(r"^```(?:json)?\s*", flags=re.IGNORECASE)
CODE_FENCE_CLOSE_RE = re.compile(r"\s*```$")


def parse_args() -> argparse.Namespace:
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
        default="prompts/multi_query.txt",
        help="Prompt template for multi-query expansion",
    )
    parser.add_argument(
        "--prompt-answer",
        default="prompts/rag_answer.txt",
        help="Prompt template for final answer synthesis",
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
    return parser.parse_args()


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


def extract_json_array(text: str) -> list[str]:
    stripped = text.strip()
    stripped = CODE_FENCE_OPEN_RE.sub("", stripped)
    stripped = CODE_FENCE_CLOSE_RE.sub("", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if isinstance(item, str) and item.strip()]


def dedup_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def expand_query(
    question: str,
    num_variants: int,
    prompt_path: Path,
    llm: Callable[[str], str],
) -> list[str]:
    template = prompt_path.read_text(encoding="utf-8")
    prompt = template.format(question=question, num_variants=num_variants)
    raw = call_with_retries(prompt, llm)

    variants = extract_json_array(raw)
    if not variants:
        logging.warning("Multi-query expansion returned no parseable variants; falling back to question only")
        return [question]

    if variants[0].strip() != question.strip():
        variants = [question, *variants]

    return dedup_preserve_order(variants)[:num_variants]


def _date_to_int(date: str) -> int:
    return int(date.replace("-", ""))


def build_where_filter(args: argparse.Namespace) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []

    if args.since:
        clauses.append({"date_int": {"$gte": _date_to_int(args.since)}})
    if args.until:
        clauses.append({"date_int": {"$lte": _date_to_int(args.until)}})
    if args.channels:
        names = [name.strip() for name in args.channels.split(",") if name.strip()]
        if names:
            clauses.append({"channel_name": {"$in": names}})
    if args.chat_ids:
        ids = [int(value.strip()) for value in args.chat_ids.split(",") if value.strip()]
        if ids:
            clauses.append({"chat_id": {"$in": ids}})
    if args.with_links_only:
        clauses.append({"has_link": True})
    if args.min_chars > 0:
        clauses.append({"text_length": {"$gte": args.min_chars}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def merge_hits(hit_lists: list[list[QueryHit]]) -> list[QueryHit]:
    by_id: dict[str, QueryHit] = {}
    for hits in hit_lists:
        for hit in hits:
            existing = by_id.get(hit.id)
            if existing is None or hit.distance < existing.distance:
                by_id[hit.id] = hit
    return sorted(by_id.values(), key=lambda h: h.distance)


def dot_product(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def mmr_rerank(hits: list[QueryHit], final_k: int, lambda_mult: float) -> list[QueryHit]:
    candidates = [hit for hit in hits if hit.embedding is not None]
    if not candidates:
        return hits[:final_k]

    remaining: list[QueryHit] = sorted(candidates, key=lambda h: h.distance)
    selected: list[QueryHit] = []

    while remaining and len(selected) < final_k:
        if not selected:
            selected.append(remaining.pop(0))
            continue

        best_index = 0
        best_score = -float("inf")
        for index, candidate in enumerate(remaining):
            relevance = 1.0 - candidate.distance
            assert candidate.embedding is not None
            max_similarity = max(
                dot_product(candidate.embedding, other.embedding) for other in selected if other.embedding is not None
            )
            score = lambda_mult * relevance - (1.0 - lambda_mult) * max_similarity
            if score > best_score:
                best_score = score
                best_index = index

        selected.append(remaining.pop(best_index))

    return selected


def format_context(hits: list[QueryHit]) -> str:
    lines: list[str] = []
    for index, hit in enumerate(hits, start=1):
        meta = hit.metadata
        channel = meta.get("channel_name") or (f"chat:{meta['chat_id']}" if "chat_id" in meta else "?")
        msg_id = meta.get("id", "?")
        date = meta.get("date", "?")
        header = f"[#{index}] channel={channel} msg_id={msg_id} date={date}"
        lines.append(header)
        lines.append(hit.document)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%d-%m-%Y-%H-%M-%S")


def resolve_output_path(args: argparse.Namespace) -> Path:
    if args.output:
        return Path(args.output)
    directory = Path(args.output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{timestamp_slug()}.md"


def main() -> None:
    args = parse_args()
    load_repo_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    device = resolve_device(args.device)
    logging.info("Embedding device: %s", device)

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    logging.info("Loading embedding model: %s", args.model)
    model = SentenceTransformer(
        args.model,
        cache_folder=str(cache_dir),
        local_files_only=args.offline,
        device=device,
    )

    collection = get_messages_collection(Path(args.chroma_path), name=args.collection)
    logging.info("Collection '%s' count: %s", args.collection, collection.count())

    llm = build_openrouter_client(args.llm_model, get_api_key(), args.base_url)

    if args.no_expand or args.num_variants <= 1:
        variants = [args.question]
    else:
        variants = expand_query(
            question=args.question,
            num_variants=args.num_variants,
            prompt_path=Path(args.prompt_multi_query),
            llm=llm,
        )

    logging.info("Query variants: %s", variants)

    where = build_where_filter(args)
    logging.info("Where filter: %s", where)

    hit_lists: list[list[QueryHit]] = []
    for variant in variants:
        vector = embed_query(model, variant)
        hits = query_items(
            collection=collection,
            vector=vector,
            top_k=args.top_k_per_query,
            where=where,
            include_embeddings=True,
        )
        logging.info("Variant '%s' -> %s hits", variant[:60], len(hits))
        hit_lists.append(hits)

    merged = merge_hits(hit_lists)
    logging.info("Merged unique hits: %s", len(merged))

    final_hits = mmr_rerank(merged, args.final_k, args.mmr_lambda)
    logging.info("Final hits after MMR: %s", len(final_hits))

    if not final_hits:
        answer = "Не нашёл релевантных сообщений под фильтры запроса."
    else:
        prompt_template = Path(args.prompt_answer).read_text(encoding="utf-8")
        prompt = prompt_template.format(
            question=args.question,
            context=format_context(final_hits),
        )
        answer = call_with_retries(prompt, llm)

    output_path = resolve_output_path(args)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(answer.rstrip() + "\n", encoding="utf-8")

    print(answer)
    logging.info("Answer written to %s", output_path)


if __name__ == "__main__":
    main()
