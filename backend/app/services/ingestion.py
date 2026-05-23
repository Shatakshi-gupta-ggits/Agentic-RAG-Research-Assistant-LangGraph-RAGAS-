"""
PDF Ingestion Pipeline
Extract → Chunk → Embed → Store in ChromaDB
"""
import os
import uuid
import hashlib
from pathlib import Path
from typing import List, Dict

import pdfplumber
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from rank_bm25 import BM25Okapi

from app.core.config import settings


# ── ChromaDB client (singleton) ──────────────────────────────────────────────
_chroma_client: chromadb.ClientAPI | None = None
_collection = None

def get_collection():
    global _chroma_client, _collection
    if _collection is None:
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        emb_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"   # lightweight, fast, good quality
        )
        _collection = _chroma_client.get_or_create_collection(
            name="documents",
            embedding_function=emb_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# ── Text extraction ───────────────────────────────────────────────────────────
def extract_text_from_pdf(file_path: str) -> str:
    """Extract all text from a PDF file using pdfplumber."""
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text.strip())
    return "\n\n".join(text_parts)


# ── Chunking ──────────────────────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = settings.CHUNK_SIZE,
               overlap: int = settings.CHUNK_OVERLAP) -> List[str]:
    """Recursive character-level chunking with overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        # Try to break at a sentence boundary
        last_period = chunk.rfind(". ")
        if last_period > chunk_size // 2:
            end = start + last_period + 1
            chunk = text[start:end]
        chunks.append(chunk.strip())
        start = end - overlap
    return [c for c in chunks if len(c) > 50]


# ── Ingest ────────────────────────────────────────────────────────────────────
def ingest_pdf(file_path: str, filename: str) -> Dict:
    """Full ingestion pipeline for a single PDF."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Deduplicate by file hash
    with open(file_path, "rb") as f:
        file_hash = hashlib.md5(f.read()).hexdigest()

    collection = get_collection()
    existing = collection.get(where={"file_hash": file_hash})
    if existing["ids"]:
        return {"status": "already_exists", "filename": filename, "chunks": len(existing["ids"])}

    # Extract + chunk
    raw_text = extract_text_from_pdf(file_path)
    chunks = chunk_text(raw_text)

    # Store in ChromaDB (embedding happens automatically via embedding_function)
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"filename": filename, "file_hash": file_hash, "chunk_index": i}
                 for i, _ in enumerate(chunks)]

    collection.add(documents=chunks, ids=ids, metadatas=metadatas)

    return {"status": "ingested", "filename": filename, "chunks": len(chunks)}


# ── Hybrid retrieval (BM25 + dense) ──────────────────────────────────────────
def hybrid_retrieve(query: str, top_k: int = settings.TOP_K_RETRIEVAL,
                    filename_filter: str | None = None) -> List[Dict]:
    """
    Hybrid retrieval:
      1. Dense retrieval via ChromaDB cosine similarity
      2. BM25 re-rank of the top candidates
    Returns merged, deduplicated results.
    """
    collection = get_collection()

    where_clause = {"filename": filename_filter} if filename_filter else None

    # Dense retrieval — fetch 3× top_k as candidates for BM25 re-rank
    results = collection.query(
        query_texts=[query],
        n_results=min(top_k * 3, collection.count() or 1),
        where=where_clause,
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    if not docs:
        return []

    # BM25 re-rank
    tokenized = [d.lower().split() for d in docs]
    bm25 = BM25Okapi(tokenized)
    bm25_scores = bm25.get_scores(query.lower().split())

    # Combine: normalise both scores then average
    max_bm25 = max(bm25_scores) or 1
    combined = []
    for i, doc in enumerate(docs):
        dense_score = 1 - distances[i]          # cosine similarity (0–1)
        bm25_norm = bm25_scores[i] / max_bm25   # normalised BM25 (0–1)
        combined_score = 0.5 * dense_score + 0.5 * bm25_norm
        combined.append({
            "content": doc,
            "metadata": metas[i],
            "score": round(combined_score, 4),
        })

    combined.sort(key=lambda x: x["score"], reverse=True)
    return combined[:top_k]


def list_documents() -> List[str]:
    """Return unique filenames in the collection."""
    collection = get_collection()
    if collection.count() == 0:
        return []
    all_meta = collection.get(include=["metadatas"])["metadatas"]
    return list({m["filename"] for m in all_meta})
