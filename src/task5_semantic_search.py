"""Task 5: deterministic semantic search over local markdown chunks."""

import math
import re

from .task4_chunking_indexing import EMBEDDING_DIM, chunk_documents, load_documents


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ỹĐđ]+", text.lower(), flags=re.UNICODE)


def hashing_vector(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    vector = [0.0] * dim
    for token in tokenize(text):
        vector[hash(token) % dim] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _load_chunks() -> list[dict]:
    return chunk_documents(load_documents())


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    query_vec = hashing_vector(query)
    results = []
    for chunk in _load_chunks():
        score = cosine(query_vec, hashing_vector(chunk["content"]))
        if score > 0:
            results.append({
                "content": chunk["content"],
                "score": float(score),
                "metadata": chunk["metadata"],
            })
    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


if __name__ == "__main__":
    for result in semantic_search("hinh phat ma tuy", top_k=5):
        print(f"[{result['score']:.3f}] {result['content'][:100]}...")
