"""End-to-end script: ingest a file, then search it."""
import sys
import uuid
from pathlib import Path

# Make sibling imports work when run as a script
sys.path.insert(0, str(Path(__file__).parent))

from loader import load_file
from chunker import chunk_text
from store import DocumentStore


def ingest(file_path: str, store: DocumentStore) -> str:
    """Load → chunk → embed → store. Returns the document ID."""
    print(f"\n📄 Loading {file_path}...")
    loaded = load_file(file_path)
    print(f"   Got {len(loaded['text'])} characters of text")
    
    print("✂️  Chunking...")
    chunks = chunk_text(loaded["text"])
    print(f"   Created {len(chunks)} chunks")
    
    doc_id = str(uuid.uuid4())[:8]   # short ID for readability
    print(f"🧠 Embedding & storing (doc_id={doc_id})...")
    store.add_chunks(chunks, loaded["metadata"], doc_id)
    print(f"   Done. Store now has {store.count()} total chunks.")
    
    return doc_id


def search(query: str, store: DocumentStore, top_k: int = 3):
    """Search the store and print results."""
    print(f"\n🔍 Searching for: {query!r}")
    results = store.search(query, top_k=top_k)
    
    if not results:
        print("   No results found.")
        return
    
    for i, r in enumerate(results, 1):
        print(f"\n--- Result {i} (distance={r['distance']:.3f}) ---")
        print(f"From: {r['metadata']['filename']} (chunk {r['metadata']['chunk_index']})")
        snippet = r["text"][:300]
        if len(r["text"]) > 300:
            snippet += "..."
        print(snippet)


def main():
    """Parse command-line arguments and run the right command."""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1]
    store = DocumentStore()
    
    if command == "ingest":
        if len(sys.argv) < 3:
            print("Error: 'ingest' requires a file path.")
            print_usage()
            sys.exit(1)
        ingest(sys.argv[2], store)
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("Error: 'search' requires a query.")
            print_usage()
            sys.exit(1)
        # Join all remaining args so the query can be multiple words
        query = " ".join(sys.argv[2:])
        search(query, store)
    
    else:
        print(f"Error: unknown command '{command}'.")
        print_usage()
        sys.exit(1)


def print_usage():
    print("Usage:")
    print("  python ingest_and_search.py ingest <file_path>")
    print("  python ingest_and_search.py search <query>")


if __name__ == "__main__":
    main()