try:
    from app.retrieval import ensure_collections
    ensure_collections()
except Exception:
    pass  # Qdrant not available (e.g. unit tests) — collections created on first use
