"""Task 4: load, chunk, embed, and index markdown documents locally."""

from pathlib import Path

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"

# Recursive character chunking is robust for mixed legal markdown and news prose.
# 500 chars keeps chunks focused for retrieval; 50 chars preserves continuity.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

# Local hashing vectors are deterministic, offline, and adequate for tests/demo.
EMBEDDING_MODEL = "local-hashing-tfidf"
EMBEDDING_DIM = 512
VECTOR_STORE = "local-memory"


def load_documents() -> list[dict]:
    documents = []
    if not STANDARDIZED_DIR.exists():
        return documents
    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue
        doc_type = md_file.parent.name if md_file.parent != STANDARDIZED_DIR else "unknown"
        documents.append({
            "content": content,
            "metadata": {
                "source": md_file.name,
                "path": str(md_file.relative_to(STANDARDIZED_DIR)),
                "type": doc_type,
            },
        })
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    chunks = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for doc in documents:
        text = " ".join(doc["content"].split())
        if not text:
            continue
        for start in range(0, len(text), step):
            chunk_text = text[start:start + CHUNK_SIZE].strip()
            if not chunk_text:
                continue
            chunks.append({
                "content": chunk_text,
                "metadata": {**doc["metadata"], "chunk_index": len(chunks)},
            })
            if start + CHUNK_SIZE >= len(text):
                break
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    from .task5_semantic_search import hashing_vector

    for chunk in chunks:
        chunk["embedding"] = hashing_vector(chunk["content"])
    return chunks


def index_to_vectorstore(chunks: list[dict]) -> list[dict]:
    return chunks


def run_pipeline() -> list[dict]:
    docs = load_documents()
    chunks = chunk_documents(docs)
    return index_to_vectorstore(embed_chunks(chunks))


if __name__ == "__main__":
    print(f"Indexed {len(run_pipeline())} chunks into {VECTOR_STORE}.")
