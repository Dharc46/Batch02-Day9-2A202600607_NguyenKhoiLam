"""Task 8: PageIndex-style vectorless fallback over local documents."""

import os
from pathlib import Path

from dotenv import load_dotenv

from .task4_chunking_indexing import chunk_documents, load_documents
from .task6_lexical_search import build_bm25_index
from .task5_semantic_search import tokenize

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"


def upload_documents() -> list[Path]:
    return sorted(STANDARDIZED_DIR.rglob("*.md")) if STANDARDIZED_DIR.exists() else []


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    chunks = chunk_documents(load_documents())
    if not chunks:
        return []

    # Vectorless fallback: structural/keyword scoring over document text.
    index = build_bm25_index(chunks)
    query_tokens = set(tokenize(query))
    results = []
    for idx, tokens in enumerate(index["tokenized"]):
        overlap = len(query_tokens & set(tokens)) / max(len(query_tokens), 1)
        if overlap == 0 and query_tokens:
            continue
        score = overlap or 0.05
        results.append({
            "content": chunks[idx]["content"],
            "score": float(score),
            "metadata": chunks[idx]["metadata"],
            "source": "pageindex",
        })
    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


if __name__ == "__main__":
    for result in pageindex_search("ma tuy", top_k=3):
        print(f"[{result['score']:.3f}] {result['content'][:100]}...")
