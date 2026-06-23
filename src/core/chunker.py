"""Splits long text into overlapping chunks suitable for embedding."""
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> list[str]:
    """
    Split text into chunks of roughly `chunk_size` characters,
    with `chunk_overlap` characters shared between adjacent chunks.
    
    Returns: a list of string chunks
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # Try splitting at paragraphs first, then sentences, then words.
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)