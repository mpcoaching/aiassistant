"""
Tests for Markdown parsing.
"""

from __future__ import annotations

import pytest

from knowledge_mcp.parser.markdown_parser import (
    build_breadcrumb,
    extract_frontmatter,
    extract_headings,
    extract_references,
    split_sections,
)


class TestExtractHeadings:
    def test_single_heading(self):
        content = "# Heading 1\n\nSome text.\n"
        headings = extract_headings(content)
        assert len(headings) == 1
        assert headings[0]["line"] == 1
        assert headings[0]["level"] == 1
        assert headings[0]["text"] == "Heading 1"

    def test_multiple_levels(self):
        content = """# Level 1
## Level 2
### Level 3
"""
        headings = extract_headings(content)
        assert len(headings) == 3
        assert headings[0]["level"] == 1
        assert headings[1]["level"] == 2
        assert headings[2]["level"] == 3

    def test_heading_line_numbers(self):
        content = "Line 1\n## Heading\nLine 3\n"
        headings = extract_headings(content)
        assert headings[0]["line"] == 2

    def test_heading_with_trailing_hashes(self):
        content = "## Heading ##\n"
        headings = extract_headings(content)
        assert len(headings) == 1
        assert headings[0]["text"] == "Heading"

    def test_no_headings(self):
        content = "Just some text.\nNo headings here.\n"
        headings = extract_headings(content)
        assert len(headings) == 0

    def test_heading_in_code_fence_ignored(self):
        content = """```markdown
# This is not a heading
```
# Real heading
"""
        headings = extract_headings(content)
        assert len(headings) == 1
        assert headings[0]["text"] == "Real heading"

    def test_heading_in_tilde_fence_ignored(self):
        content = """~~~
# Not a heading
~~~
# Real heading
"""
        headings = extract_headings(content)
        assert len(headings) == 1
        assert headings[0]["text"] == "Real heading"


class TestBuildBreadcrumb:
    def test_single_heading(self):
        headings = [{"line": 1, "level": 1, "text": "Architecture"}]
        assert build_breadcrumb(headings, 1) == "Architecture"

    def test_nested_headings(self):
        headings = [
            {"line": 1, "level": 1, "text": "Architecture"},
            {"line": 3, "level": 2, "text": "Configuration"},
            {"line": 5, "level": 3, "text": "Configuration Manager"},
        ]
        assert build_breadcrumb(headings, 3) == "Architecture > Configuration > Configuration Manager"

    def test_partial_hierarchy(self):
        headings = [
            {"line": 1, "level": 1, "text": "Architecture"},
            {"line": 3, "level": 2, "text": "Configuration"},
        ]
        assert build_breadcrumb(headings, 2) == "Architecture > Configuration"

    def test_no_headings(self):
        assert build_breadcrumb([], 1) is None

    def test_level_not_found(self):
        headings = [{"line": 1, "level": 1, "text": "Architecture"}]
        assert build_breadcrumb(headings, 3) is None


class TestSplitSections:
    def test_single_heading(self):
        content = "# Architecture\n\nContent here.\n"
        sections = split_sections(content)
        assert len(sections) == 1
        assert sections[0]["heading"] == "Architecture"
        assert sections[0]["level"] == 1
        assert sections[0]["start_line"] == 1
        assert "Content here." in sections[0]["content"]

    def test_heading_only_merged_with_content(self):
        content = """# Architecture
## Configuration
### Configuration Manager

Content under manager.
"""
        sections = split_sections(content)
        assert len(sections) == 1
        assert sections[0]["heading"] == "Configuration Manager"
        assert sections[0]["start_line"] == 1
        assert "Content under manager." in sections[0]["content"]
        assert "Architecture" in sections[0]["content"]
        assert "Configuration" in sections[0]["content"]

    def test_no_headings(self):
        content = "Just some text.\nNo headings.\n"
        sections = split_sections(content)
        assert len(sections) == 1
        assert sections[0]["heading"] is None
        assert sections[0]["level"] == 0
        assert sections[0]["start_line"] == 1
        assert sections[0]["end_line"] == 2

    def test_section_line_ranges(self):
        content = """# Heading
Line 2
## Subheading
Line 4
"""
        sections = split_sections(content)
        assert sections[0]["start_line"] == 1
        assert sections[0]["end_line"] == 2
        assert sections[1]["start_line"] == 3
        assert sections[1]["end_line"] == 4

    def test_heading_followed_by_another_heading(self):
        content = """# H1
## H2
### H3
Content.
"""
        sections = split_sections(content)
        assert len(sections) == 1
        assert sections[0]["heading"] == "H3"
        assert sections[0]["start_line"] == 1
        assert "Content." in sections[0]["content"]

    def test_last_heading_only_preserved(self):
        content = """# H1
Content.
## H2
"""
        sections = split_sections(content)
        assert len(sections) == 2
        assert sections[0]["heading"] == "H1"
        assert sections[1]["heading"] == "H2"
        assert sections[1]["content"] == "## H2"


class TestExtractFrontmatter:
    def test_valid_frontmatter(self):
        content = """---
title: Example
type: architecture
---

# Heading

Body.
"""
        metadata, remaining = extract_frontmatter(content)
        assert metadata["title"] == "Example"
        assert metadata["type"] == "architecture"
        assert "# Heading" in remaining

    def test_no_frontmatter(self):
        content = "# Heading\n\nBody.\n"
        metadata, remaining = extract_frontmatter(content)
        assert metadata == {}
        assert remaining == content

    def test_frontmatter_only(self):
        content = "---\ntitle: Only\n---\n"
        metadata, remaining = extract_frontmatter(content)
        assert metadata["title"] == "Only"
        assert remaining == ""

    def test_frontmatter_values_as_strings(self):
        content = "---\ncount: 42\nflag: true\n---\n"
        metadata, remaining = extract_frontmatter(content)
        assert metadata["count"] == "42"
        assert metadata["flag"] == "True"


class TestExtractReferences:
    def test_standard_links(self):
        content = "[Config](docs/configuration.md) and [API](docs/api.md)"
        refs = extract_references(content)
        assert refs == ["docs/api.md", "docs/configuration.md"]

    def test_wiki_links(self):
        content = "See [[Configuration]] and [[patterns/index]]"
        refs = extract_references(content)
        assert refs == ["Configuration", "patterns/index"]

    def test_mixed_links(self):
        content = "[Standard](path.md) and [[Wiki]]"
        refs = extract_references(content)
        assert refs == ["Wiki", "path.md"]

    def test_links_with_fragments(self):
        content = "[Section](#section) and [Doc](doc.md#frag)"
        refs = extract_references(content)
        assert refs == ["doc.md"]

    def test_external_urls(self):
        content = "[Qdrant](https://qdrant.tech/) and [Architecture](../architecture.md)"
        refs = extract_references(content)
        assert refs == ["../architecture.md", "https://qdrant.tech/"]

    def test_multiple_external_urls(self):
        content = "[A](https://example.com/a) and [B](https://example.com/b)"
        refs = extract_references(content)
        assert refs == ["https://example.com/a", "https://example.com/b"]

    def test_no_links(self):
        content = "Just text with no links."
        refs = extract_references(content)
        assert refs == []

    def test_deduplicates(self):
        content = "[Link](doc.md) and [Again](doc.md)"
        refs = extract_references(content)
        assert refs == ["doc.md"]
