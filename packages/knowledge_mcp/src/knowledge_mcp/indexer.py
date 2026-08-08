"""
Knowledge indexer.

Scans a corpus root for Markdown files, parses them, and produces
KnowledgeChunk objects. Does not embed, store, or expose MCP tools.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from knowledge_mcp.parser.markdown_parser import (
    extract_frontmatter,
    extract_references,
    extract_headings,
    split_sections,
)
from knowledge_mcp.store.models import KnowledgeChunk


def _compute_file_hash(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def _chunk_section(
    section: dict[str, Any],
    chunk_size: int,
    chunk_overlap: int,
    document_path: str,
    file_hash: str,
) -> list[KnowledgeChunk]:
    """Chunk a single section into KnowledgeChunk objects.

    Chunking rules:
    - If section content <= chunk_size, emit as single chunk.
    - If section content > chunk_size, split at paragraph boundaries.
    - If a single paragraph exceeds chunk_size, split at word boundaries.
    - Consecutive chunks have chunk_overlap characters of overlap.
    - Never produce empty chunks.
    """
    if chunk_size <= 0:
        chunk_size = 500
    if chunk_overlap < 0:
        chunk_overlap = 0
    if chunk_overlap >= chunk_size:
        chunk_overlap = chunk_size // 4

    section_content = section["content"]
    if not section_content.strip():
        return []

    # If section fits in one chunk, return it directly
    if len(section_content) <= chunk_size:
        return [_make_chunk(section, 0, document_path, file_hash, section_content)]

    # Split at paragraph boundaries
    paragraphs = section_content.split("\n\n")
    chunks: list[KnowledgeChunk] = []
    current_text = ""
    chunk_index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If paragraph itself exceeds chunk_size, split at word boundaries
        if len(para) > chunk_size:
            # Emit current chunk first
            if current_text.strip():
                chunks.append(_make_chunk(section, chunk_index, document_path, file_hash, current_text))
                chunk_index += 1
                current_text = ""

            # Split long paragraph into word-boundary chunks
            words = para.split()
            word_chunk = ""
            for word in words:
                test = f"{word_chunk} {word}" if word_chunk else word
                if len(test) > chunk_size and word_chunk:
                    chunks.append(_make_chunk(section, chunk_index, document_path, file_hash, word_chunk))
                    chunk_index += 1
                    overlap = _get_word_overlap(word_chunk, chunk_overlap)
                    word_chunk = f"{overlap} {word}" if overlap else word
                else:
                    word_chunk = test

            if word_chunk.strip():
                current_text = word_chunk
            continue

        # Normal paragraph fitting
        if current_text and len(current_text) + len(para) + 2 > chunk_size:
            chunks.append(_make_chunk(section, chunk_index, document_path, file_hash, current_text))
            chunk_index += 1
            overlap_text = _get_overlap(current_text, chunk_overlap)
            current_text = f"{overlap_text}\n\n{para}" if overlap_text else para
        else:
            current_text = f"{current_text}\n\n{para}" if current_text else para

    # Emit final chunk
    if current_text.strip():
        chunks.append(_make_chunk(section, chunk_index, document_path, file_hash, current_text))

    return chunks


def _get_overlap(text: str, overlap: int) -> str:
    """Get the last `overlap` characters from text for chunk overlap.

    Tries to break at a newline to avoid splitting words/paragraphs mid-stream.
    """
    if overlap <= 0 or len(text) <= overlap:
        return ""

    overlap_text = text[-overlap:]
    # Try to find a newline near the overlap boundary to avoid mid-word splits
    newline_idx = overlap_text.find("\n")
    if newline_idx != -1:
        return overlap_text[newline_idx + 1:]

    return overlap_text


def _get_word_overlap(text: str, overlap: int) -> str:
    """Get approximately `overlap` characters from text, breaking at word boundaries."""
    if overlap <= 0 or len(text) <= overlap:
        return ""

    overlap_text = text[-overlap:]
    # Break at first space to avoid mid-word splits
    space_idx = overlap_text.find(" ")
    if space_idx != -1:
        return overlap_text[space_idx + 1:]

    return overlap_text


def _make_chunk(
    section: dict[str, Any],
    chunk_index: int,
    document_path: str,
    file_hash: str,
    content: str,
) -> KnowledgeChunk:
    """Create a KnowledgeChunk from a section and chunk index."""
    heading = section.get("heading")
    level = section.get("level", 0)
    start_line = section.get("start_line", 1)
    end_line = section.get("end_line", 1)

    # Build breadcrumb from section headings
    # For now, breadcrumb is just the current heading text
    # The full hierarchy will be built by the orchestrator
    breadcrumb = _build_section_breadcrumb(section)

    chunk_id = f"{document_path}:{chunk_index}"

    # Extract references from chunk content
    references = extract_references(content)

    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_path=document_path,
        content=content,
        section_heading=heading,
        breadcrumb=breadcrumb,
        start_line=start_line,
        end_line=end_line,
        references=references,
        document_metadata={},
    )


def _build_section_breadcrumb(section: dict[str, Any]) -> str | None:
    """Build a breadcrumb string for a section.

    For v1, the breadcrumb is just the section heading text.
    The full hierarchy breadcrumb will be added by the orchestrator
    once heading hierarchy is tracked across sections.
    """
    heading = section.get("heading")
    if heading is None:
        return None
    return heading


def index_document(
    content: str,
    document_path: str,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[list[KnowledgeChunk], dict[str, Any]]:
    """Parse and chunk a Markdown document.

    Args:
        content: Raw Markdown content
        document_path: Relative path from corpus root
        chunk_size: Maximum chunk size in characters
        chunk_overlap: Overlap between consecutive chunks

    Returns:
        (chunks, document_metadata)
    """
    file_hash = _compute_file_hash(content)

    # Extract frontmatter
    metadata, remaining_content = extract_frontmatter(content)

    # Split into sections
    sections = split_sections(remaining_content)

    # Build heading hierarchy for breadcrumb construction
    headings = extract_headings(remaining_content)
    heading_map = {h["line"]: h for h in headings}

    # Chunk each section
    all_chunks: list[KnowledgeChunk] = []
    for section in sections:
        section_chunks = _chunk_section(section, chunk_size, chunk_overlap, document_path, file_hash)

        # Enhance breadcrumbs with heading hierarchy
        for chunk in section_chunks:
            enhanced = _enhance_breadcrumb(chunk, section, headings)
            all_chunks.append(enhanced)

    return all_chunks, metadata


def _enhance_breadcrumb(
    chunk: KnowledgeChunk,
    section: dict[str, Any],
    headings: list[dict[str, Any]],
) -> KnowledgeChunk:
    """Enhance a chunk's breadcrumb with full heading hierarchy.

    For a chunk under heading "Configuration Manager" at level 3, with parent
    headings "Platform" (level 1) and "Configuration" (level 2), the breadcrumb
    becomes "Platform > Configuration > Configuration Manager".
    """
    section_heading = section.get("heading")
    if not section_heading:
        return chunk

    # Find parent headings
    section_line = section.get("start_line", 1)
    parent_headings = [h["text"] for h in headings if h["line"] < section_line and h["level"] < section.get("level", 99)]

    breadcrumb_parts = parent_headings + [section_heading]
    breadcrumb = " > ".join(breadcrumb_parts)

    return chunk.model_copy(update={"breadcrumb": breadcrumb})


def scan_corpus(corpus_root: str, extensions: list[str] | None = None) -> list[Path]:
    """Scan a corpus root for Markdown files.

    Args:
        corpus_root: Root directory to scan
        extensions: File extensions to include (default: [".md", ".mdx"])

    Returns:
        Sorted list of file paths
    """
    if extensions is None:
        extensions = [".md", ".mdx"]

    root = Path(corpus_root)
    if not root.exists() or not root.is_dir():
        return []

    files: list[Path] = []
    for ext in extensions:
        files.extend(root.rglob(f"*{ext}"))

    # Filter out common non-corpus directories
    exclude_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", "target"}
    filtered: list[Path] = []
    for f in files:
        parts = set(f.relative_to(root).parts)
        if not parts.intersection(exclude_dirs):
            filtered.append(f)

    return sorted(filtered)


def read_document(path: Path) -> str:
    """Read a document file as UTF-8 text."""
    return path.read_text(encoding="utf-8")
