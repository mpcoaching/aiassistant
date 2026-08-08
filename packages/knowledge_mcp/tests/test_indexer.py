"""
Tests for corpus indexing and orchestrator.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from knowledge_mcp.indexer import index_document, scan_corpus
from knowledge_mcp.orchestrator import KnowledgeOrchestrator


class TestScanCorpus:
    def test_finds_markdown_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "doc1.md").write_text("# Doc1")
            (root / "doc2.md").write_text("# Doc2")
            (root / "readme.txt").write_text("Not markdown")

            files = scan_corpus(str(root))
            assert len(files) == 2
            assert sorted(f.name for f in files) == ["doc1.md", "doc2.md"]

    def test_recursive_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "sub").mkdir()
            (root / "sub" / "doc.md").write_text("# Nested")

            files = scan_corpus(str(root))
            assert len(files) == 1
            assert files[0].name == "doc.md"

    def test_excludes_git_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git").mkdir()
            (root / ".git" / "config.md").write_text("# Git")
            (root / "doc.md").write_text("# Real")

            files = scan_corpus(str(root))
            assert len(files) == 1
            assert files[0].name == "doc.md"

    def test_empty_corpus(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = scan_corpus(str(tmpdir))
            assert len(files) == 0

    def test_nonexistent_corpus(self):
        files = scan_corpus("/nonexistent/path/that/does/not/exist")
        assert len(files) == 0


class TestIndexDocument:
    def test_indexes_single_document(self):
        content = "# Architecture\n\nContent here.\n"
        chunks, metadata = index_document(content, "architecture.md", 500, 120)
        assert len(chunks) == 1
        assert chunks[0].document_path == "architecture.md"
        assert chunks[0].content is not None

    def test_multiple_documents_same_corpus(self):
        doc1 = "# Doc1\n\nContent 1.\n"
        doc2 = "# Doc2\n\nContent 2.\n"
        chunks1, _ = index_document(doc1, "doc1.md", 500, 120)
        chunks2, _ = index_document(doc2, "doc2.md", 500, 120)
        assert chunks1[0].document_path == "doc1.md"
        assert chunks2[0].document_path == "doc2.md"
        assert chunks1[0].chunk_id != chunks2[0].chunk_id

    def test_nested_paths_preserved(self):
        content = "# Architecture\n\nContent.\n"
        chunks, metadata = index_document(
            content,
            "agentic/docs/architecture/patterns/pat014.md",
            500,
            120,
        )
        assert chunks[0].document_path == "agentic/docs/architecture/patterns/pat014.md"

    def test_empty_markdown(self):
        chunks, metadata = index_document("", "empty.md", 500, 120)
        assert len(chunks) == 0

    def test_frontmatter_only(self):
        content = "---\ntitle: Only\n---\n"
        chunks, metadata = index_document(content, "doc.md", 500, 120)
        assert len(chunks) == 0
        assert metadata["title"] == "Only"


class TestOrchestrator:
    def test_process_corpus(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "doc1.md").write_text("# Doc1\n\nContent 1.\n")
            (root / "doc2.md").write_text("# Doc2\n\nContent 2.\n")

            orch = KnowledgeOrchestrator(str(root), chunk_size=500, chunk_overlap=120)
            results = orch.process_corpus()

            assert len(results) == 2
            assert "doc1.md" in results
            assert "doc2.md" in results
            assert len(results["doc1.md"]) == 1
            assert len(results["doc2.md"]) == 1

    def test_process_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            doc = root / "architecture.md"
            doc.write_text("# Architecture\n\nContent.\n")

            orch = KnowledgeOrchestrator(str(root), chunk_size=500, chunk_overlap=120)
            results = orch.process_document(doc)

            assert len(results) == 1
            rel_path, chunks = results[0]
            assert str(rel_path) == "architecture.md"
            assert len(chunks) == 1

    def test_process_document_produces_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sub = root / "agentic" / "docs"
            sub.mkdir(parents=True)
            doc = sub / "pattern.md"
            doc.write_text("# Pattern\n\nContent.\n")

            orch = KnowledgeOrchestrator(str(root), chunk_size=500, chunk_overlap=120)
            results = orch.process_document(doc)

            rel_path, chunks = results[0]
            assert str(rel_path) == "agentic/docs/pattern.md"
            assert chunks[0].document_path == "agentic/docs/pattern.md"
            assert not chunks[0].document_path.startswith("/")
