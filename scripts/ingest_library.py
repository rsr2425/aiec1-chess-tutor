"""Ingest public-domain chess classics into Qdrant `library` collection.

Sources (ADR 0001 — public domain only):
  - Capablanca, Chess Fundamentals (Gutenberg #33870)
  - Lasker, Common Sense in Chess (Gutenberg #6559)

Chunking strategy (TDD §8):
  - Split by the books' own chapter/section headings (natural units)
  - Sections longer than ~1500 tokens get RecursiveCharacterTextSplitter(1000/100)
  - Payload: book, author, section_title, license, source_url

Idempotent: uses hash(book + section_title + chunk_index) as Qdrant point id.
Run once from your laptop; the corpus is static for the POC.
"""

from __future__ import annotations

import hashlib
import os
import re
import urllib.request
from typing import Iterator

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# ── Config ────────────────────────────────────────────────────────────────────

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY", "")
AI_GATEWAY_BASE_URL = os.getenv("AI_GATEWAY_BASE_URL", "")

COLLECTION = "library"
VECTOR_SIZE = 1536
TOKEN_THRESHOLD = 1500  # sections longer than this get further split

BOOKS = [
    {
        "title": "Chess Fundamentals",
        "author": "José Raúl Capablanca",
        "gutenberg_id": 33870,
        "license": "public domain",
    },
    {
        "title": "Common Sense in Chess",
        "author": "Emanuel Lasker",
        "gutenberg_id": 6559,
        "license": "public domain",
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

SECTION_RE = re.compile(
    r"^(CHAPTER|LESSON|PART|Section|INTRODUCTION|PREFACE)[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)


def fetch_gutenberg(gutenberg_id: int) -> str:
    url = f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-0.txt"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            text = r.read().decode("utf-8", errors="replace")
    except Exception:
        # Fallback to plain .txt
        url = f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt"
        with urllib.request.urlopen(url, timeout=30) as r:
            text = r.read().decode("utf-8", errors="replace")

    # Strip Gutenberg header/footer boilerplate
    start = re.search(r"\*\*\* START OF THE PROJECT GUTENBERG", text)
    end = re.search(r"\*\*\* END OF THE PROJECT GUTENBERG", text)
    if start and end:
        text = text[start.end() : end.start()]
    return text.strip()


def split_by_headings(text: str) -> list[tuple[str, str]]:
    """Return [(section_title, body), ...] split on chapter headings."""
    parts = SECTION_RE.split(text)
    if len(parts) <= 1:
        # No headings found — treat as one chunk
        return [("Full text", text)]

    sections: list[tuple[str, str]] = []
    matches = list(SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        title = m.group().strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((title, body))
    return sections


def chunk_section(title: str, body: str, book: str, author: str, license_: str, source_url: str) -> Iterator[Document]:
    approx_tokens = len(body) // 4  # rough approximation
    if approx_tokens <= TOKEN_THRESHOLD:
        yield Document(
            page_content=body,
            metadata={
                "book": book,
                "author": author,
                "section_title": title,
                "license": license_,
                "source_url": source_url,
            },
        )
    else:
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = splitter.split_text(body)
        for i, chunk in enumerate(chunks):
            yield Document(
                page_content=chunk,
                metadata={
                    "book": book,
                    "author": author,
                    "section_title": f"{title} (part {i+1})",
                    "license": license_,
                    "source_url": source_url,
                },
            )


def doc_id(book: str, section: str, index: int) -> str:
    """Deterministic Qdrant point ID from content metadata."""
    key = f"{book}::{section}::{index}"
    return str(int(hashlib.md5(key.encode()).hexdigest(), 16) % (10**18))


# ── Qdrant setup ──────────────────────────────────────────────────────────────

def ensure_collection(client: QdrantClient) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION not in existing:
        client.create_collection(
            COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Created collection '{COLLECTION}'")
    else:
        print(f"Collection '{COLLECTION}' already exists — will upsert idempotently")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    ensure_collection(client)

    embed_kwargs: dict = {
        "model": EMBED_MODEL,
        "api_key": AI_GATEWAY_API_KEY,
        # Disable tiktoken pre-check — it corrupts the request body through the AI gateway
        "check_embedding_ctx_length": False,
    }
    if AI_GATEWAY_BASE_URL:
        embed_kwargs["base_url"] = AI_GATEWAY_BASE_URL + "/v1"
    embeddings = OpenAIEmbeddings(**embed_kwargs)

    store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION,
        embedding=embeddings,
    )

    total = 0
    for book in BOOKS:
        print(f"\nFetching: {book['title']} by {book['author']} …")
        source_url = f"https://www.gutenberg.org/ebooks/{book['gutenberg_id']}"
        text = fetch_gutenberg(book["gutenberg_id"])
        sections = split_by_headings(text)
        print(f"  Found {len(sections)} sections")

        docs: list[Document] = []
        for sec_title, sec_body in sections:
            for chunk in chunk_section(
                sec_title, sec_body,
                book["title"], book["author"], book["license"], source_url
            ):
                docs.append(chunk)

        print(f"  Upserting {len(docs)} chunks …")
        store.add_documents(docs)
        total += len(docs)

    print(f"\nDone. Total chunks ingested: {total}")


if __name__ == "__main__":
    main()
