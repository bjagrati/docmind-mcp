"""High-level orchestration: ties together file loading, chunking,
both storage backends, and search strategies."""
import uuid
from typing import Optional

from core.loader import load_file
from core.chunker import chunk_text
from core.store import DocumentStore
from core.metadata_store import MetadataStore


# Reciprocal Rank Fusion constant. The standard value from the original paper.
RRF_K = 60


class DocumentService:
    """
    The orchestration layer. Every interface (CLI, MCP, web) calls
    methods here rather than touching stores directly.
    """
    
    def __init__(
        self,
        vector_store: Optional[DocumentStore] = None,
        metadata_store: Optional[MetadataStore] = None,
    ):
        # Dependency injection: allow custom stores for testing,
        # default to standard locations otherwise.
        self.vectors = vector_store or DocumentStore()
        self.meta = metadata_store or MetadataStore()
    
    # ───────────────────────────── Ingest ─────────────────────────────
    
    def ingest_file(self, file_path: str) -> dict:
        """
        Full ingest pipeline. Loads the file, chunks it, embeds chunks,
        and records metadata + FTS content. Returns a summary dict.
        """
        loaded = load_file(file_path)
        chunks = chunk_text(loaded["text"])
        doc_id = str(uuid.uuid4())[:8]
        
        # Two writes that need to stay in sync. We attempt the vector
        # store first because it's the more failure-prone (embedding
        # model can fail, network etc.). If that succeeds, we record
        # metadata. If metadata fails, we roll back the vector store.
        self.vectors.add_chunks(chunks, loaded["metadata"], doc_id)
        try:
            self.meta.add_document(
                doc_id=doc_id,
                filename=loaded["metadata"]["filename"],
                filetype=loaded["metadata"]["filetype"],
                source_path=loaded["metadata"]["source_path"],
                chunks=chunks,
            )
        except Exception:
            # Best-effort cleanup of the orphaned vectors
            self._delete_vectors_for_doc(doc_id)
            raise
        
        return {
            "doc_id": doc_id,
            "filename": loaded["metadata"]["filename"],
            "chunks_created": len(chunks),
            "total_chunks": self.vectors.count(),
        }
    
    # ─────────────────────────── Search APIs ──────────────────────────
    
    def semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Pure vector search via ChromaDB."""
        raw = self.vectors.search(query, top_k=top_k)
        return [
            {
                "chunk_id": r["metadata"].get("doc_id", "?") + f"_chunk_{r['metadata'].get('chunk_index', '?')}",
                "doc_id": r["metadata"].get("doc_id"),
                "chunk_index": r["metadata"].get("chunk_index"),
                "filename": r["metadata"].get("filename"),
                "content": r["text"],
                "semantic_distance": r["distance"],
            }
            for r in raw
        ]
    
    def keyword_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Pure keyword search via SQLite FTS5."""
        raw = self.meta.keyword_search(query, top_k=top_k)
        # Attach filenames by looking each doc up in metadata
        enriched = []
        filenames: dict[str, str] = {}
        for r in raw:
            doc_id = r["doc_id"]
            if doc_id not in filenames:
                doc = self.meta.get_document(doc_id)
                filenames[doc_id] = doc["filename"] if doc else "?"
            enriched.append({
                "chunk_id": r["chunk_id"],
                "doc_id": doc_id,
                "chunk_index": r["chunk_index"],
                "filename": filenames[doc_id],
                "content": r["content"],
                "keyword_score": r["score"],
            })
        return enriched
    
    def hybrid_search(self, query: str, top_k: int = 5, candidates_per_method: int = 20) -> list[dict]:
        """
        Hybrid search using Reciprocal Rank Fusion.
        Pulls a wider candidate set from each method, then re-ranks them
        by combined RRF score. Returns the top_k after fusion.
        """
        semantic = self.semantic_search(query, top_k=candidates_per_method)
        keyword = self.keyword_search(query, top_k=candidates_per_method)
        
        # Build a unified map keyed by chunk_id
        fused: dict[str, dict] = {}
        
        for rank, item in enumerate(semantic):
            chunk_id = item["chunk_id"]
            fused.setdefault(chunk_id, {**item, "rrf_score": 0.0, "found_in": []})
            fused[chunk_id]["rrf_score"] += 1.0 / (RRF_K + rank + 1)  # rank is 0-indexed; formula expects 1-indexed
            fused[chunk_id]["found_in"].append("semantic")
        
        for rank, item in enumerate(keyword):
            chunk_id = item["chunk_id"]
            if chunk_id in fused:
                # Already there from semantic — augment with keyword score
                fused[chunk_id]["keyword_score"] = item["keyword_score"]
            else:
                fused[chunk_id] = {**item, "rrf_score": 0.0, "found_in": []}
            fused[chunk_id]["rrf_score"] += 1.0 / (RRF_K + rank + 1)
            fused[chunk_id]["found_in"].append("keyword")
        
        # Sort by RRF score descending and return top_k
        ranked = sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)
        return ranked[:top_k]
    
    # ──────────────────────── Document management ────────────────────
    
    def list_documents(self) -> list[dict]:
        return self.meta.list_documents()
    
    def get_document(self, doc_id: str) -> Optional[dict]:
        return self.meta.get_document(doc_id)
    
    def delete_document(self, doc_id: str) -> bool:
        """Remove from both stores. Returns True if anything was deleted."""
        deleted_meta = self.meta.delete_document(doc_id)
        deleted_vec = self._delete_vectors_for_doc(doc_id)
        return deleted_meta or deleted_vec
    
    def count_documents(self) -> int:
        return self.meta.count_documents()
    
    def count_chunks(self) -> int:
        return self.vectors.count()
    
    # ─────────────────────────── Internals ────────────────────────────
    
    def _delete_vectors_for_doc(self, doc_id: str) -> bool:
        """
        Delete all ChromaDB chunks belonging to a doc_id.
        Returns True if any chunks were deleted.
        """
        results = self.vectors.collection.get(where={"doc_id": doc_id})
        if not results["ids"]:
            return False
        self.vectors.collection.delete(ids=results["ids"])
        return True