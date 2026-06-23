"""Wraps ChromaDB so the rest of the code doesn't need to know about it."""
import chromadb
from chromadb.utils import embedding_functions

# Use sentence-transformers locally — free, private, runs on CPU.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class DocumentStore:
    def __init__(self, persist_dir: str = None):
        if persist_dir is None:
            from pathlib import Path
            persist_dir = str(Path(__file__).parent.parent.parent / "storage" / "chroma_db")
        self.client = chromadb.PersistentClient(path=persist_dir)
        
        # Tell ChromaDB which embedding model to use.
        # This same function will be used for both storing AND querying — 
        # guaranteeing consistency.
        self.embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        
        # A "collection" is like a table in a normal database — 
        # a named group of related vectors.
        self.collection = self.client.get_or_create_collection(
            name="documents",
            embedding_function=self.embedder,
        )
    
    def add_chunks(self, chunks: list[str], base_metadata: dict, doc_id: str):
        """Store chunks with metadata. Each chunk gets a unique ID."""
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {**base_metadata, "chunk_index": i, "doc_id": doc_id}
            for i in range(len(chunks))
        ]
        self.collection.add(ids=ids, documents=chunks, metadatas=metadatas)
    
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search. Returns the top_k most relevant chunks."""
        results = self.collection.query(query_texts=[query], n_results=top_k)
        # Chroma returns parallel lists; let's zip them into nice dicts.
        return [
            {"text": doc, "metadata": meta, "distance": dist}
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]
    
    def count(self) -> int:
        """Return the total number of stored chunks."""
        return self.collection.count()