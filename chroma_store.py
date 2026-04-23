from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

import chromadb
from chromadb.api.models.Collection import Collection

MESSAGES_COLLECTION = "messages"


class MessageMetadata(TypedDict, total=False):
    chat_id: int
    channel_name: str
    id: int
    date: str
    date_int: int
    sender_id: int
    has_link: bool
    text_length: int


MetadataScalar = str | int | float | bool
ChromaMetadataValue = MetadataScalar | list[MetadataScalar] | None
QueryInclude = Literal["documents", "embeddings", "metadatas", "distances", "uris", "data"]


@dataclass(frozen=True)
class StoreItem:
    id: str
    document: str
    embedding: Sequence[float]
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class QueryHit:
    id: str
    document: str
    metadata: dict[str, Any]
    distance: float
    embedding: list[float] | None = None


def get_messages_collection(path: Path, name: str = MESSAGES_COLLECTION) -> Collection:
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(path))
    # cosine matches the normalized e5 embeddings used elsewhere in the repo
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


def _clean_metadata(metadata: Mapping[str, object]) -> dict[str, ChromaMetadataValue]:
    cleaned: dict[str, ChromaMetadataValue] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, bool | int | float | str):
            cleaned[key] = value
    return cleaned


def upsert_items(collection: Collection, items: Iterable[StoreItem]) -> int:
    ids: list[str] = []
    documents: list[str] = []
    embeddings: list[Sequence[float]] = []
    metadatas: list[Mapping[str, ChromaMetadataValue]] = []

    for item in items:
        ids.append(item.id)
        documents.append(item.document)
        embeddings.append(item.embedding)
        metadatas.append(_clean_metadata(item.metadata))

    if not ids:
        return 0

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=cast(Any, metadatas),
    )
    return len(ids)


def query_items(
    collection: Collection,
    vector: Sequence[float],
    top_k: int,
    where: dict[str, Any] | None = None,
    include_embeddings: bool = False,
) -> list[QueryHit]:
    include: list[QueryInclude] = ["documents", "metadatas", "distances"]
    if include_embeddings:
        include.append("embeddings")

    query_embeddings: list[Sequence[float]] = [list(vector)]

    result = collection.query(
        query_embeddings=query_embeddings,
        n_results=top_k,
        where=where,
        include=include,
    )

    def first_batch(key: str) -> list[Any]:
        batch = cast(Sequence[Any] | None, result.get(key))
        if not batch:
            return []
        first = batch[0]
        return list(first) if first is not None else []

    ids = first_batch("ids")
    docs = first_batch("documents")
    metas = first_batch("metadatas")
    dists = first_batch("distances")
    embs = first_batch("embeddings") if include_embeddings else []

    hits: list[QueryHit] = []
    for index, (hit_id, document, metadata, distance) in enumerate(zip(ids, docs, metas, dists, strict=True)):
        embedding: list[float] | None = None
        if include_embeddings and index < len(embs):
            raw_emb = embs[index]
            if raw_emb is not None:
                embedding = [float(value) for value in raw_emb]

        hits.append(
            QueryHit(
                id=hit_id,
                document=document or "",
                metadata=dict(metadata) if metadata else {},
                distance=float(distance) if distance is not None else 0.0,
                embedding=embedding,
            )
        )
    return hits
