"""
Markdown parser for knowledge documents.

Handles:
- ATX heading detection with source line numbers
- Heading hierarchy and breadcrumb construction
- YAML frontmatter extraction
- Markdown link/reference extraction
- Code-fence-aware parsing (headings inside fenced blocks are ignored)
- Document splitting into sections
"""

from __future__ import annotations

import re
from typing import Any


# Matches ATX headings: #, ##, ###, etc.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")

# Matches fenced code block openings: ``` or ~~~
_FENCE_OPEN_RE = re.compile(r"^(```|~~~)")

# Matches YAML frontmatter delimiters
_FRONTMATTER_DELIM_RE = re.compile(r"^---\s*$")

# Matches Markdown links: [text](path) and [text](path "title")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# Matches wiki-style links: [[path]]
_WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def extract_headings(content: str) -> list[dict[str, Any]]:
    """Extract ATX headings with line numbers.

    Headings inside fenced code blocks are ignored.

    Returns a list of dicts with keys:
    - line: 1-based line number
    - level: heading depth (1-6)
    - text: heading text (stripped)
    """
    headings: list[dict[str, Any]] = []
    lines = content.splitlines()
    in_fence = False
    fence_char = ""

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Track fenced code blocks
        fence_match = _FENCE_OPEN_RE.match(stripped)
        if fence_match:
            fence_char = fence_match.group(1)
            in_fence = not in_fence
            continue

        if in_fence:
            continue

        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            headings.append({
                "line": i,
                "level": level,
                "text": text,
            })

    return headings


def build_breadcrumb(headings: list[dict[str, Any]], target_level: int) -> str | None:
    """Build a heading breadcrumb from the hierarchy up to target_level.

    Example:
        headings at levels 1, 2, 3 -> "Level1 > Level2 > Level3"

    Returns None if no headings exist or target_level is not found.
    """
    if not headings:
        return None

    # Find the target heading
    target = None
    for h in headings:
        if h["level"] == target_level:
            target = h
            break

    if target is None:
        return None

    # Collect parent headings (levels less than target_level)
    parts: list[str] = [h["text"] for h in headings if h["level"] < target_level]
    parts.append(target["text"])

    return " > ".join(parts)


def split_sections(content: str) -> list[dict[str, Any]]:
    """Split Markdown content into sections based on ATX headings.

    Returns a list of section dicts with keys:
    - heading: heading text or None for preamble
    - level: heading depth (1-6) or 0 for preamble
    - start_line: 1-based start line
    - end_line: 1-based end line
    - content: section text including the heading line
    """
    lines = content.splitlines()
    sections: list[dict[str, Any]] = []

    # Track heading positions
    heading_positions: list[tuple[int, int, str]] = []  # (line, level, text)

    in_fence = False
    fence_char = ""

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        fence_match = _FENCE_OPEN_RE.match(stripped)
        if fence_match:
            fence_char = fence_match.group(1)
            in_fence = not in_fence
            continue

        if in_fence:
            continue

        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            heading_positions.append((i, level, text))

    # Build sections from heading positions
    if not heading_positions:
        # No headings: entire document is one section
        sections.append({
            "heading": None,
            "level": 0,
            "start_line": 1,
            "end_line": len(lines),
            "content": content,
        })
        return sections

    # Preamble (content before first heading)
    first_heading_line = heading_positions[0][0]
    if first_heading_line > 1:
        preamble_lines = lines[:first_heading_line - 1]
        sections.append({
            "heading": None,
            "level": 0,
            "start_line": 1,
            "end_line": first_heading_line - 1,
            "content": "\n".join(preamble_lines),
        })

    # Heading sections
    for idx, (line, level, text) in enumerate(heading_positions):
        end_line = heading_positions[idx + 1][0] - 1 if idx + 1 < len(heading_positions) else len(lines)
        section_lines = lines[line - 1:end_line]
        sections.append({
            "heading": text,
            "level": level,
            "start_line": line,
            "end_line": end_line,
            "content": "\n".join(section_lines),
        })

    return sections


def extract_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter from Markdown content.

    Returns:
        (metadata_dict, remaining_content)
    """
    lines = content.splitlines()
    if not lines or not _FRONTMATTER_DELIM_RE.match(lines[0].strip()):
        return {}, content

    # Find closing ---
    end_idx = None
    for i in range(1, len(lines)):
        if _FRONTMATTER_DELIM_RE.match(lines[i].strip()):
            end_idx = i
            break

    if end_idx is None:
        return {}, content

    frontmatter_text = "\n".join(lines[1:end_idx])
    remaining = "\n".join(lines[end_idx + 1:])

    try:
        import yaml
        metadata = yaml.safe_load(frontmatter_text) or {}
        if not isinstance(metadata, dict):
            metadata = {}
    except Exception:
        metadata = {}

    # Convert all values to strings for consistency
    metadata = {str(k): str(v) for k, v in metadata.items()}

    return metadata, remaining


def extract_references(content: str) -> list[str]:
    """Extract document references from Markdown content.

    Finds:
    - [text](path) links
    - [[path]] wiki-style links

    Returns a list of unique reference targets.
    """
    references: set[str] = set()

    for match in _MD_LINK_RE.finditer(content):
        target = match.group(2).strip()
        # Remove URL fragments and query strings for cleaner references
        if "#" in target:
            target = target.split("#")[0]
        if target:
            references.add(target)

    for match in _WIKI_LINK_RE.finditer(content):
        target = match.group(1).strip()
        if target:
            references.add(target)

    return sorted(references)
