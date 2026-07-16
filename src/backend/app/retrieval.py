"""Qdrant retrieval — collections, embedders, and retrievers.

Three collections:
    library         public-domain chess classics (shared)
    moments         key positions from student games (filtered by user_id)
    game_summaries  one paragraph per game (filtered by user_id)

Task 6 upgrade path: swap the dense-only retriever for BM25 + dense ensemble.
The retriever interface stays the same; only this file changes.
"""

from __future__ import annotations

import os
from typing import Optional

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, MatchValue

_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
_QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
_EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
_AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY", "")
_AI_GATEWAY_BASE_URL = os.getenv("AI_GATEWAY_BASE_URL", "")

VECTOR_SIZE = 1536  # text-embedding-3-small

# Collection names
LIBRARY = "library"
MOMENTS = "moments"
GAME_SUMMARIES = "game_summaries"


def _embeddings() -> OpenAIEmbeddings:
    kwargs: dict = {
        "model": _EMBED_MODEL,
        "api_key": _AI_GATEWAY_API_KEY,
        # Disable tiktoken pre-check — it corrupts the request body through the AI gateway
        "check_embedding_ctx_length": False,
    }
    if _AI_GATEWAY_BASE_URL:
        kwargs["base_url"] = _AI_GATEWAY_BASE_URL + "/v1"
    return OpenAIEmbeddings(**kwargs)


def _qdrant_client() -> QdrantClient:
    if _QDRANT_API_KEY:
        return QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_API_KEY)
    return QdrantClient(url=_QDRANT_URL)


def ensure_collections() -> None:
    """Idempotently create collections. Call at startup or from ingest script."""
    client = _qdrant_client()
    existing = {c.name for c in client.get_collections().collections}
    for name in [LIBRARY, MOMENTS, GAME_SUMMARIES]:
        if name not in existing:
            client.create_collection(
                name,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )


# ── Dense retrievers (baseline — Task 5) ─────────────────────────────────────


def library_retriever(k: int = 4):
    store = QdrantVectorStore.from_existing_collection(
        embedding=_embeddings(),
        collection_name=LIBRARY,
        url=_QDRANT_URL,
        api_key=_QDRANT_API_KEY or None,
    )
    dense = store.as_retriever(search_kwargs={"k": k})
    if os.getenv("USE_ENSEMBLE_RETRIEVER", "").lower() not in ("1", "true", "yes"):
        return dense
    return _library_ensemble_retriever(dense, k=k)


def moments_retriever(user_id: str, k: int = 4):
    store = QdrantVectorStore.from_existing_collection(
        embedding=_embeddings(),
        collection_name=MOMENTS,
        url=_QDRANT_URL,
        api_key=_QDRANT_API_KEY or None,
    )
    return store.as_retriever(
        search_kwargs={
            "k": k,
            "filter": Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
        }
    )


def game_summaries_retriever(user_id: str, k: int = 3):
    store = QdrantVectorStore.from_existing_collection(
        embedding=_embeddings(),
        collection_name=GAME_SUMMARIES,
        url=_QDRANT_URL,
        api_key=_QDRANT_API_KEY or None,
    )
    return store.as_retriever(
        search_kwargs={
            "k": k,
            "filter": Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
        }
    )


# ── Upsert helpers ────────────────────────────────────────────────────────────


def upsert_moment(moment_doc: Document) -> None:
    """Embed and upsert a single Moment document into the `moments` collection."""
    store = QdrantVectorStore.from_existing_collection(
        embedding=_embeddings(),
        collection_name=MOMENTS,
        url=_QDRANT_URL,
        api_key=_QDRANT_API_KEY or None,
    )
    store.add_documents([moment_doc])


def upsert_game_summary(summary_doc: Document) -> None:
    """Embed and upsert a Game Summary document into the `game_summaries` collection."""
    store = QdrantVectorStore.from_existing_collection(
        embedding=_embeddings(),
        collection_name=GAME_SUMMARIES,
        url=_QDRANT_URL,
        api_key=_QDRANT_API_KEY or None,
    )
    store.add_documents([summary_doc])


# ── Task 6: ensemble retriever (BM25 + dense) ────────────────────────────────
# Enabled with USE_ENSEMBLE_RETRIEVER=true. The library corpus is static for
# the POC, so the BM25 index is built once per process and cached.

_bm25_retriever = None


def _library_ensemble_retriever(dense, k: int = 4):
    global _bm25_retriever
    try:
        from langchain.retrievers import EnsembleRetriever
    except ImportError:  # langchain >= 1.0 moved it
        from langchain_classic.retrievers import EnsembleRetriever
    from langchain_community.retrievers import BM25Retriever

    if _bm25_retriever is None:
        points, _ = _qdrant_client().scroll(
            collection_name=LIBRARY, limit=1000, with_payload=True
        )
        docs = [
            Document(
                page_content=p.payload.get("page_content", ""),
                metadata=p.payload.get("metadata", {}),
            )
            for p in points
            if p.payload.get("page_content")
        ]
        _bm25_retriever = BM25Retriever.from_documents(docs, k=k)
    _bm25_retriever.k = k
    return EnsembleRetriever(retrievers=[_bm25_retriever, dense], weights=[0.5, 0.5])
