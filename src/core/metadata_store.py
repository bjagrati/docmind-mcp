"""SQLite-backed metadata store with FTS5 keyword search."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


# Build absolute path the same way store.py does, so it works from any cwd
_DEFAULT_DB_PATH = str(
    Path(__file__).parent.parent.parent / "storage" / "metadata.sqlite"
)


class MetadataStore:
    """
    Tracks document-level metadata in a regular table, and chunk content
    in a separate FTS5 virtual table for keyword search.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        # Make sure the parent folder exists (sqlite3 won't create it)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    def _connect(self) -> sqlite3.Connection:
        """
        Open a new SQLite connection. We use row_factory so query results
        come back as dict-like rows (accessible by column name) instead of
        positional tuples.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_schema(self):
        """Create tables if they don't exist. Idempotent — safe to run repeatedly."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id        TEXT PRIMARY KEY,
                    filename      TEXT NOT NULL,
                    filetype      TEXT,
                    source_path   TEXT,
                    chunk_count   INTEGER NOT NULL DEFAULT 0,
                    uploaded_at   TEXT NOT NULL
                );
                
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id      UNINDEXED,
                    doc_id        UNINDEXED,
                    chunk_index   UNINDEXED,
                    content,
                    tokenize = 'porter unicode61'
                );
            """)
    
    def add_document(
        self,
        doc_id: str,
        filename: str,
        filetype: str,
        source_path: str,
        chunks: list[str],
    ):
        """
        Record a document and all its chunks atomically.
        Both the documents row and the FTS chunks are inserted in one transaction.
        """
        uploaded_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (doc_id, filename, filetype, source_path, chunk_count, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_id, filename, filetype, source_path, len(chunks), uploaded_at),
            )
            
            # Insert each chunk into the FTS index
            chunk_rows = [
                (f"{doc_id}_chunk_{i}", doc_id, i, chunk_text)
                for i, chunk_text in enumerate(chunks)
            ]
            conn.executemany(
                "INSERT INTO chunks_fts (chunk_id, doc_id, chunk_index, content) VALUES (?, ?, ?, ?)",
                chunk_rows,
            )
    
    def list_documents(self) -> list[dict]:
        """Return all documents, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY uploaded_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_document(self, doc_id: str) -> Optional[dict]:
        """Return one document's metadata, or None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
            return dict(row) if row else None
    
    def delete_document(self, doc_id: str) -> bool:
        """Remove a document and all its chunks. Returns True if a document was deleted."""
        with self._connect() as conn:
            # Delete chunks from FTS first
            conn.execute("DELETE FROM chunks_fts WHERE doc_id = ?", (doc_id,))
            cursor = conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            return cursor.rowcount > 0
    
    def keyword_search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Full-text search over chunk content using FTS5 with BM25 ranking.
        Lower bm25 score = better match (it's a distance-like measure here).
        """
        # Sanitize: FTS5 has its own query syntax (quotes, AND, OR, NEAR).
        # For safety, escape double quotes and wrap each token to treat the
        # input as plain words rather than FTS5 syntax.
        safe_query = self._sanitize_query(query)
        if not safe_query:
            return []
        
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    chunk_id,
                    doc_id,
                    chunk_index,
                    content,
                    bm25(chunks_fts) AS score
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (safe_query, top_k),
            ).fetchall()
            return [dict(row) for row in rows]
    
    def count_documents(self) -> int:
        """Total number of documents in the catalog."""
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    
    @staticmethod
    def _sanitize_query(query: str) -> str:
        """
        Convert a user's free-text query into a safe FTS5 query string.
        We split on whitespace and wrap each token in double quotes,
        then join with spaces (implicit AND in FTS5).
        """
        tokens = [t for t in query.strip().split() if t]
        # Escape any double-quote characters inside tokens
        quoted = [f'"{t.replace(chr(34), "")}"' for t in tokens]
        return " ".join(quoted)