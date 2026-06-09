"""Task 7: reranking utilities."""

from .task5_semantic_search import cosine, hashing_vector, tokenize


def rerank_cross_encoder(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    query_tokens = set(tokenize(query))
    query_vec = hashing_vector(query)
    reranked = []
    for candidate in candidates:
        content = candidate.get("content", "")
        content_tokens = set(tokenize(content))
        lexical_overlap = len(query_tokens & content_tokens) / max(len(query_tokens), 1)
        semantic = cosine(query_vec, hashing_vector(content))
        original = float(candidate.get("score", 0.0))
        item = candidate.copy()
        item["score"] = 0.45 * semantic + 0.35 * lexical_overlap + 0.20 * original
        reranked.append(item)
    return sorted(reranked, key=lambda item: item["score"], reverse=True)[:top_k]


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    if not candidates:
        return []
    embeddings = [item.get("embedding") or hashing_vector(item.get("content", "")) for item in candidates]
    selected: list[int] = []
    remaining = list(range(len(candidates)))

    while remaining and len(selected) < top_k:
        best_idx = remaining[0]
        best_score = float("-inf")
        for idx in remaining:
            relevance = cosine(query_embedding, embeddings[idx])
            diversity_penalty = max((cosine(embeddings[idx], embeddings[s]) for s in selected), default=0.0)
            score = lambda_param * relevance - (1 - lambda_param) * diversity_penalty
            if score > best_score:
                best_idx = idx
                best_score = score
        selected.append(best_idx)
        remaining.remove(best_idx)

    results = []
    for idx in selected:
        item = candidates[idx].copy()
        item["score"] = float(cosine(query_embedding, embeddings[idx]))
        results.append(item)
    return results


def rerank_rrf(ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = item.get("metadata", {}).get("path") or item.get("content", "")
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            items[key] = item

    results = []
    for key, score in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:top_k]:
        item = items[key].copy()
        item["score"] = float(score)
        results.append(item)
    return results


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "cross_encoder",
) -> list[dict]:
    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    if method == "mmr":
        return rerank_mmr(hashing_vector(query), candidates, top_k)
    if method == "rrf":
        return rerank_rrf([candidates], top_k)
    raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    docs = [
        {"content": "Toi tang tru ma tuy", "score": 0.8, "metadata": {}},
        {"content": "Python programming", "score": 0.7, "metadata": {}},
    ]
    print(rerank("hinh phat ma tuy", docs, top_k=1))
