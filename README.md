# docmind-mcp

A semantic + keyword document retrieval system with three interfaces:

- 🤖 **MCP server** — Claude (or any MCP-compatible AI) can search your documents as tools
- 🌐 **Web app** — upload, browse, and search documents via a clean browser UI
- 💻 **CLI** — power-user command line for scripting and automation

All three interfaces share one engine: a hybrid retrieval pipeline combining vector embeddings (ChromaDB) and keyword search (SQLite FTS5), fused via Reciprocal Rank Fusion.

Built as a learning project to explore RAG, MCP, and full-stack AI engineering from first principles.

---

## What It Does

Upload text files, Markdown, or PDFs. Then search them three ways:

- **Semantic** — find chunks by *meaning*. Search "how do robots learn" and find a passage about reinforcement learning, even if the word "robots" never appears.
- **Keyword** — find chunks containing literal words. Backed by SQLite FTS5 with BM25 scoring and Porter stemming.
- **Hybrid** — combine both methods using Reciprocal Rank Fusion (RRF) for the best results.

---

## Architecture

The codebase follows a **hexagonal architecture**: a shared `core/` engine, plus multiple `interfaces/` that wrap it.

\`\`\`
┌──────────────────────────────────────────────────────────────────┐
│                            USERS                                  │
│   Web browser     AI agent (Claude)    Power user (terminal)     │
└────────┬──────────────────┬──────────────────┬──────────────────┘
         │ HTTP             │ stdio (MCP)      │ subprocess
┌────────▼────────┐ ┌──────▼──────┐  ┌────────▼───────┐
│   FastAPI       │ │   MCP        │  │   CLI          │
│   web server    │ │   server     │  │                │
└────────┬────────┘ └──────┬──────┘  └────────┬───────┘
         └────────────────┬┴─────────────────┘
                          │
                  ┌───────▼────────┐
                  │  DocumentService   │   ← orchestration layer
                  └───────┬────────┘
                          │
            ┌─────────────┼─────────────┐
            │             │             │
   ┌────────▼────┐ ┌─────▼─────┐  ┌────▼─────────┐
   │  ChromaDB   │ │  SQLite   │  │  loader.py,  │
   │  (vectors)  │ │  (catalog │  │  chunker.py  │
   │             │ │  + FTS5)  │  │              │
   └─────────────┘ └───────────┘  └──────────────┘
\`\`\`

### Components

| Path                                | Role                                                            |
| ----------------------------------- | --------------------------------------------------------------- |
| `src/core/loader.py`                | Reads .txt, .md, .pdf files into plain text                     |
| `src/core/chunker.py`               | Recursive text splitting with overlap                           |
| `src/core/store.py`                 | ChromaDB wrapper for vector storage and semantic search         |
| `src/core/metadata_store.py`        | SQLite catalog + FTS5 keyword search with BM25 + Porter stemming |
| `src/core/service.py`               | Orchestration layer with hybrid search via Reciprocal Rank Fusion |
| `src/interfaces/cli.py`             | Command-line interface                                          |
| `src/interfaces/mcp_server.py`      | MCP server (FastMCP) exposing tools to Claude                   |
| `src/interfaces/web/api.py`         | FastAPI REST endpoints                                          |
| `src/interfaces/web/static/`        | HTML/CSS/JS frontend                                            |

---

## Tech Stack

- **Python 3.12**
- **FastAPI + Uvicorn** — REST API and ASGI server
- **ChromaDB** — local vector database
- **SQLite + FTS5** — relational catalog and keyword search (no external dependency)
- **sentence-transformers** (`all-MiniLM-L6-v2`) — text embeddings, runs locally
- **PyMuPDF** — PDF text extraction
- **langchain-text-splitters** — smart recursive chunking
- **MCP Python SDK (FastMCP)** — MCP server protocol
- **Pydantic** — request/response validation
- **Plain HTML/CSS/JS** — frontend (no framework)

---

## Setup

### Prerequisites

- Python 3.10+ (3.12 recommended)
- macOS, Linux, or Windows

### Install

\`\`\`bash
git clone https://github.com/bjagrati/docmind-mcp.git
cd docmind-mcp

python3.12 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
\`\`\`

---

## Usage

### Web app (recommended)

\`\`\`bash
uvicorn src.interfaces.web.api:app --reload --port 8000
\`\`\`

Then open:
- **http://localhost:8000/ui/** — the document upload + search UI
- **http://localhost:8000/docs** — interactive API documentation (Swagger UI)

### CLI

\`\`\`bash
cd src/interfaces
python cli.py ingest ../../data/documents/your_file.pdf
python cli.py search "your natural-language query"
\`\`\`

### MCP integration (Claude Desktop)

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

\`\`\`json
{
  "mcpServers": {
    "docmind": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/src/interfaces/mcp_server.py"]
    }
  }
}
\`\`\`

Restart Claude Desktop. Four tools will be available:

- `search_documents(query, top_k)` — semantic search
- `list_documents()` — catalog summary
- `get_document_chunks(doc_id)` — fetch full document
- `ingest_document(file_path)` — add new files on the fly

---

## API Endpoints

| Method   | Path                       | Purpose                              |
| -------- | -------------------------- | ------------------------------------ |
| `GET`    | `/`                        | API info                             |
| `GET`    | `/stats`                   | Document and chunk counts            |
| `GET`    | `/documents`               | List all documents                   |
| `GET`    | `/documents/{doc_id}`      | Fetch one document's metadata        |
| `POST`   | `/documents/upload`        | Upload and ingest a file             |
| `DELETE` | `/documents/{doc_id}`      | Remove a document                    |
| `POST`   | `/search/semantic`         | Vector-based search                  |
| `POST`   | `/search/keyword`          | FTS5 keyword search with BM25        |
| `POST`   | `/search/hybrid`           | Combined search via RRF (recommended) |

See `/docs` once the server is running for the full interactive spec.

---

## Project Status

🎉 **v2 complete.** Current state:

- [x] Document loader (txt, md, pdf)
- [x] Smart recursive text chunking with overlap
- [x] Vector storage with ChromaDB
- [x] Semantic search
- [x] MCP server + Claude Desktop integration
- [x] CLI
- [x] SQLite catalog with FTS5 keyword search
- [x] Hybrid search via Reciprocal Rank Fusion
- [x] FastAPI REST API
- [x] Web frontend (HTML/CSS/JS)
- [ ] Multi-user authentication
- [ ] Reranking with cross-encoder
- [ ] Deployment (Railway/Render)
- [ ] Evaluation harness

---

## Roadmap

1. Deploy to a public URL (Railway or Render)
2. Add reranking via cross-encoder for retrieval quality
3. Build a small evaluation harness with metrics (precision@k, MRR)
4. Multi-user mode with simple username-based isolation
5. More file types (.docx, .html)

---

## License

MIT

---

## Author

Built by Jagrati Bhardwaj as a learning project to explore RAG, MCP, and full-stack AI engineering from first principles.