"""MCP server exposing our document retrieval engine as tools for Claude."""
import sys
from pathlib import Path

# Same path trick as ingest_and_search.py: ensure we can import our sibling modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from core.loader import load_file
from core.chunker import chunk_text
from core.store import DocumentStore

# Use absolute path for storage so it works regardless of where the server is launched from
STORAGE_PATH = str(Path(__file__).parent.parent / "storage" / "chroma_db")

# Create the MCP server with a name (this is how it'll show up in Claude Desktop)
mcp = FastMCP("docmind")

# Create one shared store instance the tools will use
store = DocumentStore(persist_dir=STORAGE_PATH)


@mcp.tool()
def search_documents(query: str, top_k: int = 5) -> str:
    """
    Search the document library by semantic meaning. Use this whenever the user
    asks a question that might be answered by their stored documents.
    
    Args:
        query: A natural-language search query (e.g., "what is reinforcement learning")
        top_k: How many results to return. Default 5. Use higher (10-15) for broad
               questions, lower (2-3) for specific lookups.
    
    Returns:
        A formatted string listing the most relevant document chunks, each with
        its source filename, chunk index, and similarity distance (lower is better).
    """
    results = store.search(query, top_k=top_k)
    
    if not results:
        return "No documents in the store yet. Use the ingest_document tool to add some."
    
    output_lines = [f"Found {len(results)} results for: {query!r}\n"]
    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        output_lines.append(
            f"--- Result {i} (distance={r['distance']:.3f}) ---\n"
            f"Source: {meta['filename']} (chunk {meta['chunk_index']}, doc_id={meta['doc_id']})\n"
            f"Content:\n{r['text']}\n"
        )
    return "\n".join(output_lines)


@mcp.tool()
def list_documents() -> str:
    """
    List basic information about what's currently stored in the document library.
    Useful when the user asks "what do I have?" or "what documents are available?"
    
    Returns:
        A summary of unique documents in the store, with chunk counts per document.
    """
    # We need to peek at all stored items and group by doc_id.
    # ChromaDB's .get() with no filter returns everything.
    all_items = store.collection.get()
    
    if not all_items["ids"]:
        return "The document store is empty. Use ingest_document to add files."
    
    # Group chunk counts by doc_id and remember the filename for each
    from collections import defaultdict
    doc_info = defaultdict(lambda: {"chunks": 0, "filename": "?", "filetype": "?"})
    for meta in all_items["metadatas"]:
        doc_id = meta["doc_id"]
        doc_info[doc_id]["chunks"] += 1
        doc_info[doc_id]["filename"] = meta.get("filename", "?")
        doc_info[doc_id]["filetype"] = meta.get("filetype", "?")
    
    lines = [f"Document store contains {len(doc_info)} document(s), {len(all_items['ids'])} total chunks:\n"]
    for doc_id, info in doc_info.items():
        lines.append(f"  • {info['filename']} ({info['filetype']}) — doc_id={doc_id}, {info['chunks']} chunks")
    
    return "\n".join(lines)


@mcp.tool()
def get_document_chunks(doc_id: str) -> str:
    """
    Fetch all chunks of a specific document in order, given its doc_id.
    Use this when the user wants the full content of a known document, not just
    search snippets. Get doc_ids first via list_documents or search_documents.
    
    Args:
        doc_id: The 8-character document ID (e.g., "a3f9b2c1")
    
    Returns:
        The full text of the document, with chunks concatenated in order.
    """
    # Use ChromaDB's metadata filtering to fetch only this doc's chunks
    results = store.collection.get(where={"doc_id": doc_id})
    
    if not results["ids"]:
        return f"No document found with doc_id '{doc_id}'. Try list_documents to see what's available."
    
    # Sort the chunks by chunk_index so they appear in original order
    chunks_with_index = sorted(
        zip(results["documents"], results["metadatas"]),
        key=lambda pair: pair[1]["chunk_index"],
    )
    
    filename = chunks_with_index[0][1].get("filename", "unknown")
    full_text = "\n".join(chunk for chunk, _ in chunks_with_index)
    
    return f"Full content of {filename} (doc_id={doc_id}):\n\n{full_text}"


@mcp.tool()
def ingest_document(file_path: str) -> str:
    """
    Load a file from disk, chunk it, embed it, and add it to the document store.
    Supports .txt, .md, and .pdf files. Use this when the user asks to add a new
    document to their library.
    
    Args:
        file_path: Absolute path to the file (e.g., "/Users/me/notes.md")
    
    Returns:
        A confirmation message with the new doc_id and chunk count.
    """
    import uuid
    
    try:
        loaded = load_file(file_path)
    except FileNotFoundError:
        return f"Error: file not found at {file_path}"
    except ValueError as e:
        return f"Error: {e}"
    
    chunks = chunk_text(loaded["text"])
    doc_id = str(uuid.uuid4())[:8]
    store.add_chunks(chunks, loaded["metadata"], doc_id)
    
    return (
        f"Successfully ingested {loaded['metadata']['filename']}.\n"
        f"  - doc_id: {doc_id}\n"
        f"  - chunks created: {len(chunks)}\n"
        f"  - total chunks in store: {store.count()}"
    )


if __name__ == "__main__":
    # Run the server with stdio transport (what Claude Desktop expects)
    mcp.run(transport="stdio")