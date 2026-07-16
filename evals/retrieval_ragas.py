"""Retrieval evaluation using Ragas — Task 5.1 / 6.1.

Evaluates the `library` retriever with Ragas metrics:
  - faithfulness
  - answer_relevancy
  - context_precision
  - context_recall

Test set = 12 hand-written golden questions + ~30 synthetic questions generated
once from random library chunks and cached to evals/testset.jsonl, so baseline
and ensemble runs are scored on identical questions.

Run with:
    make eval-retrieval                       # baseline (dense)
    make eval-retrieval RETRIEVER=ensemble    # BM25 + dense

Results are written to evals/results/retrieval_{retriever}_{ts}.md.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import types
from datetime import datetime
from pathlib import Path

# ragas 0.4.x unconditionally imports ChatVertexAI, which langchain-community
# 0.4 removed. Stub it out — ragas only uses it for isinstance checks.
_stub = types.ModuleType("langchain_community.chat_models.vertexai")


class _ChatVertexAI:  # pragma: no cover
    pass


_stub.ChatVertexAI = _ChatVertexAI
sys.modules.setdefault("langchain_community.chat_models.vertexai", _stub)

# Lazy imports so the script fails helpfully if deps are missing
try:
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient
    from datasets import Dataset
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Run: uv sync --extra eval (from src/backend)")

EVALS_DIR = Path(__file__).parent
RESULTS_DIR = EVALS_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)
TESTSET_PATH = EVALS_DIR / "testset.jsonl"

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY", "")
AI_GATEWAY_BASE_URL = os.getenv("AI_GATEWAY_BASE_URL", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "openai/gpt-4.1-mini")

N_SYNTHETIC = 30

# Hand-written golden questions grounded in the two ingested books
GOLDEN_QUESTIONS = [
    {
        "question": "What does Capablanca say a player should study first: openings, middle-game, or endings?",
        "ground_truth": "Capablanca insists the endgame should be studied first, since endings can be studied by themselves and the last phase of the game decides the result.",
    },
    {
        "question": "According to Capablanca, what should you do with your pawns when the opponent has a bishop?",
        "ground_truth": "Capablanca advises keeping your pawns on squares of the opposite colour to the opponent's bishop so they cannot be attacked by it.",
    },
    {
        "question": "What does Capablanca consider the salient weakness of doubled pawns?",
        "ground_truth": "Doubled pawns are a positional weakness because they cannot defend each other and are hard to mobilise, especially in the endgame.",
    },
    {
        "question": "How does Capablanca describe the value of a passed pawn in the endgame?",
        "ground_truth": "A passed pawn is a powerful endgame asset: it must be pushed or blockaded, ties down enemy pieces, and often decides the game by threatening to queen.",
    },
    {
        "question": "What is Lasker's rule about how many pieces to develop before undertaking an attack?",
        "ground_truth": "Lasker's common-sense rules say to develop the pieces quickly — knights before bishops — and not to launch an attack before development is complete.",
    },
    {
        "question": "Does Lasker recommend developing knights or bishops first in the opening?",
        "ground_truth": "Lasker recommends developing knights before bishops.",
    },
    {
        "question": "What does Lasker say about moving the same piece twice in the opening?",
        "ground_truth": "Lasker warns against moving a piece twice in the opening; you should not move pieces repeatedly before development is finished.",
    },
    {
        "question": "According to Lasker, at what point in the game should you attack?",
        "ground_truth": "Lasker says to attack only when you have an advantage and development is complete; premature attacks are unsound.",
    },
    {
        "question": "What does Capablanca say about exchanging pieces when you are ahead in material?",
        "ground_truth": "When ahead in material, Capablanca advises exchanging pieces (not pawns) to simplify toward a winning endgame.",
    },
    {
        "question": "How does Capablanca explain the relative value of knight versus bishop?",
        "ground_truth": "Capablanca explains a bishop is usually stronger than a knight in open positions and endings with pawns on both wings, while knights are better in blocked positions; two bishops are generally stronger than two knights.",
    },
    {
        "question": "What does Capablanca teach about the opposition of kings in pawn endings?",
        "ground_truth": "Capablanca teaches that taking the opposition — placing your king directly opposing the enemy king with an odd number of squares between — is the key manoeuvre that decides king-and-pawn endings.",
    },
    {
        "question": "What general principle does Lasker give for defending a cramped or inferior position?",
        "ground_truth": "Lasker advises the defender to remain calm, avoid weakening pawn moves, exchange attacking pieces, and seek counterplay rather than passively waiting.",
    },
]


def _llm():
    kwargs = {"model": CHAT_MODEL, "api_key": AI_GATEWAY_API_KEY, "temperature": 0}
    if AI_GATEWAY_BASE_URL:
        kwargs["base_url"] = AI_GATEWAY_BASE_URL + "/v1"
    return ChatOpenAI(**kwargs)


def _embeddings():
    kwargs = {
        "model": EMBED_MODEL,
        "api_key": AI_GATEWAY_API_KEY,
        # Disable tiktoken pre-check — it corrupts the request body through the AI gateway
        "check_embedding_ctx_length": False,
    }
    if AI_GATEWAY_BASE_URL:
        kwargs["base_url"] = AI_GATEWAY_BASE_URL + "/v1"
    return OpenAIEmbeddings(**kwargs)


def _qdrant_store() -> QdrantVectorStore:
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    return QdrantVectorStore(client=client, collection_name="library", embedding=_embeddings())


def _library_retriever(ensemble: bool = False, k: int = 4):
    store = _qdrant_store()
    dense = store.as_retriever(search_kwargs={"k": k})

    if not ensemble:
        return dense

    # Task 6: BM25 + dense ensemble
    from langchain.retrievers import EnsembleRetriever
    from langchain_community.retrievers import BM25Retriever
    from langchain_core.documents import Document

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    points, _ = client.scroll(collection_name="library", limit=1000, with_payload=True)
    docs = [
        Document(
            page_content=p.payload.get("page_content", ""),
            metadata=p.payload.get("metadata", {}),
        )
        for p in points
        if p.payload.get("page_content")
    ]
    bm25 = BM25Retriever.from_documents(docs, k=k)
    return EnsembleRetriever(retrievers=[bm25, dense], weights=[0.5, 0.5])


def build_testset() -> list[dict]:
    """Golden + synthetic questions. Generated once, cached for fair comparisons."""
    if TESTSET_PATH.exists():
        items = [json.loads(line) for line in TESTSET_PATH.read_text().splitlines() if line.strip()]
        print(f"Loaded cached testset: {len(items)} questions ({TESTSET_PATH})")
        return items

    print(f"Generating testset: {len(GOLDEN_QUESTIONS)} golden + {N_SYNTHETIC} synthetic …")
    items = [dict(q, source="golden") for q in GOLDEN_QUESTIONS]

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    points, _ = client.scroll(collection_name="library", limit=1000, with_payload=True)
    chunks = [p.payload.get("page_content", "") for p in points if p.payload.get("page_content")]
    random.seed(42)
    sampled = random.sample(chunks, min(N_SYNTHETIC, len(chunks)))

    llm = _llm()
    for i, chunk in enumerate(sampled):
        prompt = (
            "You are building a retrieval-eval testset for a chess-instruction corpus.\n"
            "From the passage below, write ONE question a club player might ask that this "
            "passage answers, and a one-sentence ground-truth answer taken from the passage.\n"
            'Respond as JSON only: {"question": "...", "ground_truth": "..."}\n\n'
            f"Passage:\n{chunk[:2000]}"
        )
        try:
            raw = llm.invoke(prompt).content.strip()
            if raw.startswith("```"):
                raw = raw.strip("`").removeprefix("json").strip()
            qa = json.loads(raw)
            if qa.get("question") and qa.get("ground_truth"):
                items.append(
                    {"question": qa["question"], "ground_truth": qa["ground_truth"], "source": "synthetic"}
                )
        except Exception as e:  # skip malformed generations
            print(f"  synthetic {i}: skipped ({e})")

    with TESTSET_PATH.open("w") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")
    print(f"Testset written: {len(items)} questions → {TESTSET_PATH}")
    return items


def run_eval(retriever_name: str = "baseline"):
    ensemble = retriever_name == "ensemble"
    retriever = _library_retriever(ensemble=ensemble)
    testset = build_testset()

    samples = {"question": [], "answer": [], "contexts": [], "ground_truth": []}

    llm = _llm()
    for i, item in enumerate(testset):
        docs = retriever.invoke(item["question"])
        contexts = [d.page_content for d in docs]
        context_str = "\n\n".join(contexts[:4])
        prompt = f"Answer based only on the context:\n\n{context_str}\n\nQuestion: {item['question']}"
        answer = llm.invoke(prompt).content

        samples["question"].append(item["question"])
        samples["answer"].append(answer)
        samples["contexts"].append(contexts)
        samples["ground_truth"].append(item["ground_truth"])
        print(f"  [{i + 1}/{len(testset)}] answered: {item['question'][:70]}")

    dataset = Dataset.from_dict(samples)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        embeddings=_embeddings(),
    )
    return result


def summarize(result) -> dict[str, float]:
    """Extract metric means across ragas versions."""
    if isinstance(result, dict):
        return {k: v for k, v in result.items() if isinstance(v, float)}
    repr_dict = getattr(result, "_repr_dict", None)
    if repr_dict:
        return {k: v for k, v in repr_dict.items() if isinstance(v, float)}
    df = result.to_pandas()
    metric_cols = [c for c in df.columns if df[c].dtype.kind == "f"]
    return {c: float(df[c].mean()) for c in metric_cols}


def write_results(summary: dict[str, float], retriever_name: str, n_questions: int) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"retrieval_{retriever_name}_{ts}.md"

    lines = [
        f"# Retrieval Eval — {retriever_name} — {ts}",
        "",
        f"Corpus: Qdrant `library` · Test set: {n_questions} questions (12 golden + synthetic, "
        f"cached in `evals/testset.jsonl`) · Generator/judge: {CHAT_MODEL}",
        "",
        "| Metric | Score |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v:.4f} |" for k, v in summary.items()]

    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nResults written to {out_path}")
    for k, v in summary.items():
        print(f"  {k}: {v:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--retriever",
        choices=["baseline", "ensemble"],
        default=os.getenv("RETRIEVER", "baseline"),
    )
    args = parser.parse_args()

    print(f"Running retrieval eval with {args.retriever} retriever …")
    result = run_eval(args.retriever)
    summary = summarize(result)
    n = len(build_testset())
    write_results(summary, args.retriever, n)


if __name__ == "__main__":
    main()
