"""Retrieval evaluation using Ragas — Task 5.1 / 6.1.

Evaluates the `library` retriever (and optionally `moments`) with Ragas metrics:
  - faithfulness
  - answer_relevancy
  - context_precision
  - context_recall

Run with:
    uv run python evals/retrieval_ragas.py [--retriever baseline|ensemble]

Results are written to evals/results/retrieval_{retriever}.md.
"""

from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime
from pathlib import Path

# Lazy imports so the script fails helpfully if deps are missing
try:
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from ragas.testset import TestsetGenerator
    from ragas.testset.graph import KnowledgeGraph
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient
    from datasets import Dataset
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Run: uv pip install ragas datasets langchain-openai langchain-qdrant")

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY", "")
AI_GATEWAY_BASE_URL = os.getenv("AI_GATEWAY_BASE_URL", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "openai/gpt-4.1-mini")


def _llm():
    kwargs = {"model": CHAT_MODEL, "api_key": AI_GATEWAY_API_KEY, "temperature": 0}
    if AI_GATEWAY_BASE_URL:
        kwargs["base_url"] = AI_GATEWAY_BASE_URL + "/v1"
    return ChatOpenAI(**kwargs)


def _embeddings():
    kwargs = {"model": EMBED_MODEL, "api_key": AI_GATEWAY_API_KEY}
    if AI_GATEWAY_BASE_URL:
        kwargs["base_url"] = AI_GATEWAY_BASE_URL + "/v1"
    return OpenAIEmbeddings(**kwargs)


def _library_retriever(ensemble: bool = False, k: int = 4):
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    store = QdrantVectorStore(
        client=client, collection_name="library", embedding=_embeddings()
    )
    dense = store.as_retriever(search_kwargs={"k": k})

    if not ensemble:
        return dense

    # Task 6: BM25 + dense ensemble
    from langchain.retrievers import EnsembleRetriever
    from langchain_community.retrievers import BM25Retriever

    docs = store.similarity_search("chess", k=500)  # load corpus for BM25
    bm25 = BM25Retriever.from_documents(docs, k=k)
    return EnsembleRetriever(retrievers=[bm25, dense], weights=[0.5, 0.5])


def run_eval(retriever_name: str = "baseline") -> dict:
    ensemble = retriever_name == "ensemble"
    retriever = _library_retriever(ensemble=ensemble)

    # Golden questions — hand-written for the Library collection
    golden_questions = [
        {
            "question": "What does Capablanca say about the importance of pawn structure?",
            "ground_truth": "Capablanca emphasizes that pawn structure determines the long-term strategic direction of the game.",
        },
        {
            "question": "How does Lasker recommend handling a material advantage?",
            "ground_truth": "Lasker advises simplifying the position and exchanging pieces when ahead in material.",
        },
        {
            "question": "What is Capablanca's advice about piece development in the opening?",
            "ground_truth": "Capablanca stresses rapid development and control of the center before launching attacks.",
        },
        {
            "question": "How should a player approach an endgame with rooks according to Lasker?",
            "ground_truth": "Lasker explains that rook endgames require activating the rook before the king.",
        },
    ]

    samples = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }

    llm = _llm()
    for item in golden_questions:
        docs = retriever.invoke(item["question"])
        contexts = [d.page_content for d in docs]
        # Generate answer from context
        context_str = "\n\n".join(contexts[:3])
        prompt = f"Answer based only on the context:\n\n{context_str}\n\nQuestion: {item['question']}"
        answer = llm.invoke(prompt).content

        samples["question"].append(item["question"])
        samples["answer"].append(answer)
        samples["contexts"].append(contexts)
        samples["ground_truth"].append(item["ground_truth"])

    dataset = Dataset.from_dict(samples)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        embeddings=_embeddings(),
    )
    return result


def write_results(result: dict, retriever_name: str) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"retrieval_{retriever_name}_{ts}.md"

    rows = [(k, f"{v:.4f}") for k, v in result.items() if isinstance(v, float)]

    lines = [
        f"# Retrieval Eval — {retriever_name} — {ts}\n",
        "| Metric | Score |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in rows]

    out_path.write_text("\n".join(lines))
    print(f"Results written to {out_path}")
    for k, v in rows:
        print(f"  {k}: {v}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retriever", choices=["baseline", "ensemble"], default="baseline")
    args = parser.parse_args()

    print(f"Running retrieval eval with {args.retriever} retriever …")
    result = run_eval(args.retriever)
    write_results(result, args.retriever)


if __name__ == "__main__":
    main()
