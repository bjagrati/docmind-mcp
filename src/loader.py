"""Reads different file types and returns plain text + metadata."""
from pathlib import Path
import fitz  # this is pymupdf


def load_file(file_path: str) -> dict:
    """
    Load a file and return its text content and metadata.
    Returns: {"text": str, "metadata": dict}
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"No file at: {file_path}")
    
    suffix = path.suffix.lower()
    metadata = {
        "filename": path.name,
        "filetype": suffix,
        "source_path": str(path.absolute()),
    }
    
    if suffix in [".txt", ".md"]:
        text = path.read_text(encoding="utf-8")
    elif suffix == ".pdf":
        text = _load_pdf(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    
    return {"text": text, "metadata": metadata}


def _load_pdf(path: Path) -> str:
    """Extract text from each page, separated by page markers."""
    doc = fitz.open(path)
    pages = []
    for page_num, page in enumerate(doc, start=1):
        pages.append(f"[Page {page_num}]\n{page.get_text()}")
    doc.close()
    return "\n\n".join(pages)