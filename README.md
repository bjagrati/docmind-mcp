# docmind-mcp

A semantic document retrieval system designed to be exposed as an MCP (Model Context Protocol) server, so AI agents like Claude can search and reason over your personal documents.

## What It Does

Ingest text files, Markdown, and PDFs into a local vector database, then search them by *meaning* — not just keywords. Built as a learning project to explore RAG (Retrieval-Augmented Generation) and MCP from scratch.

**Example:**
- A document mentions "reinforcement learning" and "AlphaGo"
- You search for `"how do robots learn"`
- The system finds the relevant chunk, even though "robots" never appears in the text

## Architecture

### Components

| File | Role |
|------|------|
| `src/loader.py` | Reads `.txt`, `.md`, and `.pdf` files into plain text |
| `src/chunker.py` | Splits long text into overlapping chunks at natural boundaries |
| `src/store.py` | Wraps ChromaDB; handles embedding, storage, and search |
| `src/ingest_and_search.py` | Command-line tool tying everything together |

## Tech Stack

- **Python 3.12**
- **ChromaDB** — local vector database
- **sentence-transformers** (`all-MiniLM-L6-v2`) — text embeddings, runs locally
- **PyMuPDF** — PDF text extraction
- **langchain-text-splitters** — smart recursive chunking

## Setup

### Prerequisites
- Python 3.10+ (3.12 recommended)
- macOS, Linux, or Windows

### Install

```bash
# Clone the repo
git clone https://github.com/bjagrati/docmind-mcp.git
cd docmind-mcp

# Create a virtual environment
python3.12 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install dependencies
pip install chromadb sentence-transformers pymupdf langchain-text-splitters
```

## Usage

### Ingest a document

```bash
cd src
python ingest_and_search.py ingest ../data/documents/your_file.pdf
```

### Search

```bash
python ingest_and_search.py search "your natural language query"
```

## MCP Integration

This project exposes its retrieval engine as an MCP server, allowing Claude Desktop (or any MCP-compatible AI client) to use it as tools.

### Available Tools

- **`search_documents(query, top_k)`** — semantic search over the document library
- **`list_documents()`** — summary of what's stored
- **`get_document_chunks(doc_id)`** — fetch all chunks of a specific document, in order
- **`ingest_document(file_path)`** — add a new document on the fly

### Configuring Claude Desktop

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

\`\`\`json
{
  "mcpServers": {
    "docmind": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/src/server.py"]
    }
  }
}
\`\`\`

Then restart Claude Desktop. The `docmind` tools should appear in the tools panel.

## Project Status

🚧 **In active development.** Current state:

- [x] Document loader (txt, md, pdf)
- [x] Smart text chunking with overlap
- [x] Vector storage with ChromaDB
- [x] Semantic search via CLI
- [x] MCP server wrapper
- [x] Claude Desktop integration verified
- [ ] Hybrid search (vector + keyword)
- [ ] Reranking with cross-encoder
- [ ] Multi-document filtering

## Roadmap

1. Wrap the retrieval engine in an MCP server (FastMCP)
2. Connect to Claude Desktop and test agentic search
3. Add reranking for better retrieval quality
4. Support metadata filters (date, file type, tags)

## License

MIT (or your choice)

## Author

Built by Jagrati Bhardwaj as a learning project for understanding RAG and MCP from first principles.