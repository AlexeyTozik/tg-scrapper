from typing import Any, Protocol

from .chroma_store import QueryHit


class FilterOptions(Protocol):
    @property
    def since(self) -> str | None: ...

    @property
    def until(self) -> str | None: ...

    @property
    def channels(self) -> str | None: ...

    @property
    def chat_ids(self) -> str | None: ...

    @property
    def with_links_only(self) -> bool: ...

    @property
    def min_chars(self) -> int: ...


def _date_to_int(date: str) -> int:
    return int(date.replace("-", ""))


def build_where_filter(options: FilterOptions) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []

    if options.since:
        clauses.append({"date_int": {"$gte": _date_to_int(options.since)}})
    if options.until:
        clauses.append({"date_int": {"$lte": _date_to_int(options.until)}})
    if options.channels:
        names = [name.strip() for name in options.channels.split(",") if name.strip()]
        if names:
            clauses.append({"channel_name": {"$in": names}})
    if options.chat_ids:
        ids = [int(value.strip()) for value in options.chat_ids.split(",") if value.strip()]
        if ids:
            clauses.append({"chat_id": {"$in": ids}})
    if options.with_links_only:
        clauses.append({"has_link": True})
    if options.min_chars > 0:
        clauses.append({"text_length": {"$gte": options.min_chars}})

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
