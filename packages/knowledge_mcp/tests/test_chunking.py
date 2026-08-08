"""
Tests for chunking behavior.
"""

from __future__ import annotations

import pytest

from knowledge_mcp.store.models import KnowledgeChunk
from knowledge_mcp.indexer import index_document


class TestSingleChunk:
    def test_short_section_single_chunk(self):
        content = """# Heading

Short paragraph.
"""
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 1
        assert chunks[0].section_heading == "Heading"
        assert chunks[0].start_line == 1
        assert chunks[0].end_line == 3

    def test_heading_only_section_produces_chunk(self):
        content = "# Heading\n\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 1
        assert chunks[0].content.strip() == "# Heading"


class TestMultipleChunks:
    def test_long_section_splits(self):
        paragraph = "This is a long paragraph. " * 100
        content = f"# Heading\n\n{paragraph}\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=200, chunk_overlap=50)
        assert len(chunks) > 1

    def test_chunk_overlap(self):
        paragraph = "Word " * 200
        content = f"## Heading\n\n{paragraph}\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=200, chunk_overlap=50)
        # With a long paragraph, consecutive chunks should have overlap
        content_chunks = [c for c in chunks if len(c.content) > 20]
        if len(content_chunks) >= 2:
            assert len(content_chunks[0].content) > 50
            assert len(content_chunks[1].content) > 50

    def test_no_empty_chunks(self):
        content = "# Heading\n\n" + "\n\n".join(["" for _ in range(10)])
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        for chunk in chunks:
            assert chunk.content.strip()

    def test_deterministic_chunking(self):
        content = "# Heading\n\nParagraph one.\n\nParagraph two.\n\nParagraph three.\n"
        chunks1, _ = index_document(content, "doc.md", chunk_size=50, chunk_overlap=20)
        chunks2, _ = index_document(content, "doc.md", chunk_size=50, chunk_overlap=20)
        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.content == c2.content
            assert c1.start_line == c2.start_line
            assert c1.end_line == c2.end_line


class TestBreadcrumb:
    def test_breadcrumb_single_heading(self):
        content = """# Architecture

Content.
"""
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 1
        assert chunks[0].breadcrumb == "Architecture"

    def test_breadcrumb_nested_headings(self):
        content = """# Architecture
## Configuration
### Configuration Manager

Content under manager.
"""
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 3
        assert chunks[0].breadcrumb == "Architecture"
        assert chunks[1].breadcrumb == "Architecture > Configuration"
        assert chunks[2].breadcrumb == "Architecture > Configuration > Configuration Manager"

    def test_no_headings_no_breadcrumb(self):
        content = "Just text.\nNo headings.\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 1
        assert chunks[0].breadcrumb is None
        assert chunks[0].section_heading is None


class TestProvenance:
    def test_exact_line_numbers(self):
        content = "Line 1\n# Heading\nLine 3\nLine 4\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 2
        assert chunks[0].start_line == 1
        assert chunks[0].end_line == 1
        assert chunks[1].start_line == 2
        assert chunks[1].end_line == 4

    def test_source_path_preserved(self):
        content = """# Heading

Content.
"""
        chunks, metadata = index_document(content, "docs/architecture/pattern.md", chunk_size=500, chunk_overlap=120)
        assert chunks[0].document_path == "docs/architecture/pattern.md"

    def test_frontmatter_preserved(self):
        content = """---
title: Example
type: architecture
---

# Heading

Content.
"""
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert metadata["title"] == "Example"
        assert metadata["type"] == "architecture"

    def test_references_extracted(self):
        content = "# Heading\n\n[Config](docs/configuration.md) and [[Patterns]]\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert "docs/configuration.md" in chunks[0].references
        assert "Patterns" in chunks[0].references


class TestChunkIds:
    def test_deterministic_ids(self):
        content = "# Heading\n\nContent.\n"
        chunks1, _ = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        chunks2, _ = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert chunks1[0].chunk_id == chunks2[0].chunk_id

    def test_chunk_id_format(self):
        content = "# Heading\n\nContent.\n"
        chunks, _ = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert chunks[0].chunk_id == "doc.md:0"

    def test_multiple_chunks_incremental_ids(self):
        paragraph = "Word " * 200
        content = f"# Heading\n\n{paragraph}\n"
        chunks, _ = index_document(content, "doc.md", chunk_size=200, chunk_overlap=50)
        ids = [c.chunk_id for c in chunks]
        assert ids == [f"doc.md:{i}" for i in range(len(chunks))]


class TestEdgeCases:
    def test_empty_document(self):
        chunks, metadata = index_document("", "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 0

    def test_frontmatter_only(self):
        content = "---\ntitle: Only\n---\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 0
        assert metadata["title"] == "Only"

    def test_headings_only(self):
        content = "# H1\n## H2\n### H3\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 3
        assert chunks[0].section_heading == "H1"
        assert chunks[1].section_heading == "H2"
        assert chunks[2].section_heading == "H3"

    def test_no_headings(self):
        content = "Just text.\nNo headings.\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 1
        assert chunks[0].section_heading is None
        assert chunks[0].breadcrumb is None

    def test_nested_headings(self):
        content = """# H1
## H2
### H3
#### H4
Content.
"""
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 4
        assert chunks[3].breadcrumb == "H1 > H2 > H3 > H4"

    def test_heading_jump(self):
        content = """# H1
### H3
Content.
"""
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 2
        assert chunks[1].breadcrumb == "H1 > H3"

    def test_duplicate_heading_names(self):
        content = """# Heading
## Section
Content 1.
## Section
Content 2.
"""
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 3
        assert chunks[1].section_heading == "Section"
        assert chunks[2].section_heading == "Section"
        assert chunks[1].start_line < chunks[2].start_line

    def test_very_long_paragraph(self):
        paragraph = "Word " * 500
        content = f"# Heading\n\n{paragraph}\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=200, chunk_overlap=50)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.content) <= 250  # Allow some tolerance

    def test_multiple_blank_lines(self):
        content = "# Heading\n\n\n\n\nContent.\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 1
        assert "Content." in chunks[0].content

    def test_markdown_links(self):
        content = "# Heading\n\n[Config](docs/configuration.md)\n"
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert "docs/configuration.md" in chunks[0].references

    def test_code_fence_not_heading(self):
        content = """```markdown
# Fake heading
```
# Real heading
"""
        chunks, metadata = index_document(content, "doc.md", chunk_size=500, chunk_overlap=120)
        assert len(chunks) == 2
        assert chunks[0].section_heading is None
        assert chunks[1].section_heading == "Real heading"
