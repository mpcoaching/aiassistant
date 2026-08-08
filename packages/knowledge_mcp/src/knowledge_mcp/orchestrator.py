"""
Knowledge orchestrator.

Coordinates corpus root -> file discovery -> Markdown parsing -> chunking
-> KnowledgeChunk objects. Independent of Qdrant, embeddings, and MCP tools.
"""

from __future__ import annotations

from pathlib import Path

from knowledge_mcp.indexer import index_document, scan_corpus


class KnowledgeOrchestrator:
    """Orchestrates knowledge document processing."""

    def __init__(self, corpus_root: str, chunk_size: int = 500, chunk_overlap: int = 120) -> None:
        self.corpus_root = corpus_root
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def discover(self) -> list[Path]:
        """Discover Markdown files in the corpus root."""
        return scan_corpus(self.corpus_root)

    def process_document(self, path: Path) -> list[tuple[Path, list]]:
        """Process a single document.

        Args:
            path: Absolute path to the document

        Returns:
            List of (document_path, chunks) tuples
        """
        rel_path = path.relative_to(Path(self.corpus_root))
        content = path.read_text(encoding="utf-8")
        chunks, _metadata = index_document(
            content=content,
            document_path=str(rel_path),
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        return [(rel_path, chunks)]

    def process_corpus(self) -> dict[str, list]:
        """Process all documents in the corpus.

        Returns:
            Dict mapping document_path -> list of KnowledgeChunk objects
        """
        results: dict[str, list] = {}
        for path in self.discover():
            rel_path = path.relative_to(Path(self.corpus_root))
            content = path.read_text(encoding="utf-8")
            chunks, _metadata = index_document(
                content=content,
                document_path=str(rel_path),
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            results[str(rel_path)] = chunks
        return results
