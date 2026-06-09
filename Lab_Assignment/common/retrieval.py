"""Local retrieval helpers for the distributed legal agents.

The database is the markdown corpus under data/standardized. Retrieval reuses
the existing local hybrid pipeline from src/task9_retrieval_pipeline.py.
"""

from __future__ import annotations

from functools import lru_cache


DEFAULT_TOP_K = 4
MAX_CHARS_PER_CHUNK = 700


@lru_cache(maxsize=128)
def retrieve_context(query: str, top_k: int = DEFAULT_TOP_K) -> tuple[dict, ...]:
    """Return relevant chunks from data/standardized for a query."""
    from src.task9_retrieval_pipeline import retrieve

    results = retrieve(
        query,
        top_k=top_k,
        score_threshold=0.0,
        use_reranking=True,
    )
    return tuple(results)


def format_context(query: str, top_k: int = DEFAULT_TOP_K) -> str:
    """Format retrieved chunks with source metadata for prompt injection."""
    chunks = retrieve_context(query, top_k=top_k)
    if not chunks:
        return "No matching database context was found in data/standardized."

    sections: list[str] = []
    for index, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        path = metadata.get("path") or metadata.get("source") or "unknown"
        doc_type = metadata.get("type", "unknown")
        score = float(chunk.get("score", 0.0))
        content = " ".join(chunk.get("content", "").split())
        if len(content) > MAX_CHARS_PER_CHUNK:
            content = content[:MAX_CHARS_PER_CHUNK].rstrip() + "..."
        sections.append(
            f"[{index}] source={path} type={doc_type} score={score:.3f}\n{content}"
        )
    return "\n\n".join(sections)


def build_grounded_question(question: str, role: str, top_k: int = DEFAULT_TOP_K) -> str:
    """Attach local database context to an agent question."""
    context = format_context(f"{role}: {question}", top_k=top_k)
    return (
        f"User question:\n{question}\n\n"
        "Local database context from data/standardized:\n"
        f"{context}\n\n"
        "Use the local database context where relevant. Cite sources by the bracketed "
        "source numbers like [1], [2]. If the retrieved context is not relevant, say so "
        "briefly and rely on general legal reasoning."
    )
