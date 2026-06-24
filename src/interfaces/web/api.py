"""FastAPI app exposing the document service over HTTP."""
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Path trick: ensure 'core.*' imports work when uvicorn launches us
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.service import DocumentService


# ──────────────── Pydantic request/response models ────────────────

class SearchRequest(BaseModel):
    """Common request body for all search endpoints."""
    query: str = Field(..., description="Natural language search query")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to return")


class IngestResponse(BaseModel):
    doc_id: str
    filename: str
    chunks_created: int
    total_chunks: int


class StatsResponse(BaseModel):
    documents: int
    chunks: int


# ─────────────────────────── App setup ────────────────────────────

app = FastAPI(
    title="docmind",
    description="Semantic + keyword document search service",
    version="2.0.0",
)

# One service instance shared by every request. Initialized at startup.
service = DocumentService()


# ──────────────────────── Health / info ───────────────────────────

@app.get("/", tags=["meta"])
def root():
    """Health check and API info."""
    return {
        "name": "docmind",
        "version": "2.0.0",
        "docs": "/docs",
        "ui": "/ui",
        "endpoints": ["/documents", "/search/semantic", "/search/keyword", "/search/hybrid"],
    }


@app.get("/stats", response_model=StatsResponse, tags=["meta"])
def stats():
    """Total document and chunk counts."""
    return StatsResponse(
        documents=service.count_documents(),
        chunks=service.count_chunks(),
    )


# ───────────────────────── Documents ──────────────────────────────

@app.get("/documents", tags=["documents"])
def list_documents():
    """List all documents in the catalog, newest first."""
    return {"documents": service.list_documents()}


@app.get("/documents/{doc_id}", tags=["documents"])
def get_document(doc_id: str):
    """Fetch metadata for a single document."""
    doc = service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"No document with doc_id '{doc_id}'")
    return doc


@app.post("/documents/upload", response_model=IngestResponse, tags=["documents"])
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a .txt, .md, or .pdf file. The server saves it to a temp location,
    runs the ingest pipeline (load → chunk → embed → store), then deletes the
    temp file. Returns the new doc_id and chunk count.
    """
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".txt", ".md", ".pdf"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: .txt, .md, .pdf",
        )
    
    # Stream the uploaded bytes to a temp file on disk so loader can read it.
    # delete=False because we need to close the handle before passing the path.
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name
        
        result = service.ingest_file(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
    finally:
        # Always clean up the temp file, success or failure
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except (NameError, OSError):
            pass
    
    # Replace the temp filename with the original one for a cleaner response
    result["filename"] = file.filename
    return IngestResponse(**result)


@app.delete("/documents/{doc_id}", tags=["documents"])
def delete_document(doc_id: str):
    """Remove a document and all its chunks from both stores."""
    deleted = service.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No document with doc_id '{doc_id}'")
    return {"deleted": True, "doc_id": doc_id}


# ─────────────────────────── Search ───────────────────────────────

@app.post("/search/semantic", tags=["search"])
def search_semantic(req: SearchRequest):
    """Search by meaning using vector embeddings."""
    return {"results": service.semantic_search(req.query, top_k=req.top_k)}


@app.post("/search/keyword", tags=["search"])
def search_keyword(req: SearchRequest):
    """Search by literal word matching using SQLite FTS5 with BM25."""
    return {"results": service.keyword_search(req.query, top_k=req.top_k)}


@app.post("/search/hybrid", tags=["search"])
def search_hybrid(req: SearchRequest):
    """Combined search using Reciprocal Rank Fusion (recommended)."""
    return {"results": service.hybrid_search(req.query, top_k=req.top_k)}

# ─────────────────────────── Static UI ────────────────────────────
# Serve the frontend at /ui to avoid colliding with API routes.
# The UI's JavaScript will call the JSON endpoints above.
_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/ui", StaticFiles(directory=str(_STATIC_DIR), html=True), name="ui")