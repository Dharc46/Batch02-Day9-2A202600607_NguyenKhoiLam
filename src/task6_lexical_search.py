"""Task 6: BM25 lexical search implemented without external services."""

import math
from collections import Counter

from .task4_chunking_indexing import chunk_documents, load_documents
from .task5_semantic_search import tokenize

CORPUS: list[dict] = []


def build_bm25_index(corpus: list[dict]) -> dict:
    tokenized = [tokenize(doc["content"]) for doc in corpus]
    document_frequency = Counter()
    for tokens in tokenized:
        document_frequency.update(set(tokens))
    avgdl = sum(len(tokens) for tokens in tokenized) / max(len(tokenized), 1)
    return {"tokenized": tokenized, "df": document_frequency, "avgdl": avgdl, "n": len(tokenized)}


def _load_corpus() -> list[dict]:
    global CORPUS
    if not CORPUS:
        CORPUS = chunk_documents(load_documents())
    return CORPUS


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    corpus = _load_corpus()
    index = build_bm25_index(corpus)
    query_tokens = tokenize(query)
    k1 = 1.5
    b = 0.75
    scored = []

    for idx, tokens in enumerate(index["tokenized"]):
        counts = Counter(tokens)
        score = 0.0
        dl = len(tokens)
        for token in query_tokens:
            if token not in counts:
                continue
            df = index["df"][token]
            idf = math.log(1 + (index["n"] - df + 0.5) / (df + 0.5))
            tf = counts[token]
            denom = tf + k1 * (1 - b + b * dl / max(index["avgdl"], 1))
            score += idf * (tf * (k1 + 1)) / denom
        if score > 0:
            scored.append({
                "content": corpus[idx]["content"],
                "score": float(score),
                "metadata": corpus[idx]["metadata"],
            })
    if scored:
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]
    return [
        {
            "content": item["content"],
            "score": 0.0,
            "metadata": item["metadata"],
        }
        for item in corpus[:top_k]
    ]


if __name__ == "__main__":
    for result in lexical_search("ma tuy", top_k=5):
        print(f"[{result['score']:.3f}] {result['content'][:100]}...")
