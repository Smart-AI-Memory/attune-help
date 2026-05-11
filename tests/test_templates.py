"""Tests for attune_help.templates — file resolution, parsing, caching."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from attune_help.templates import (
    _find_template_file,
    _parse_template_file,
    _PARSED_TEMPLATE_CACHE,
    invalidate_cross_links_cache,
    invalidate_template_cache,
)


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    invalidate_template_cache()
    invalidate_cross_links_cache()


def _write_template(
    base: Path,
    template_id: str,
    *,
    body: str = "Body text.",
    title: str = "Sample",
    extra_frontmatter: str = "",
) -> Path:
    """Write a minimal markdown template with frontmatter."""
    prefix, name = template_id.split("-", 1)
    type_dir = {
        "com": "comparisons",
        "con": "concepts",
        "err": "errors",
        "faq": "faqs",
        "gui": "guides",
        "not": "notes",
        "qui": "quickstarts",
        "ref": "references",
        "tas": "tasks",
        "tip": "tips",
        "tro": "troubleshooting",
        "war": "warnings",
    }[prefix]
    target = base / type_dir
    target.mkdir(parents=True, exist_ok=True)
    file = target / f"{name}.md"
    fm_block = f'name: "{name}"\nsubtype: "test"\n{extra_frontmatter}'.strip()
    file.write_text(
        f"---\n{fm_block}\n---\n\n# {title}\n\n## Overview\n\n{body}\n",
        encoding="utf-8",
    )
    return file


# ---------------------------------------------------------------------------
# _find_template_file
# ---------------------------------------------------------------------------


def test_find_template_file_resolves_known_prefix(tmp_path: Path) -> None:
    f = _write_template(tmp_path, "con-auth")
    found = _find_template_file("con-auth", tmp_path)
    assert found == f


def test_find_template_file_returns_none_for_unknown_prefix(tmp_path: Path) -> None:
    assert _find_template_file("xyz-anything", tmp_path) is None


def test_find_template_file_returns_none_for_malformed_id(tmp_path: Path) -> None:
    assert _find_template_file("noseparator", tmp_path) is None
    assert _find_template_file("", tmp_path) is None


def test_find_template_file_returns_none_when_missing(tmp_path: Path) -> None:
    # Valid prefix but file does not exist.
    assert _find_template_file("con-missing", tmp_path) is None


def test_find_template_file_blocks_path_traversal(tmp_path: Path) -> None:
    """CWE-22 guard: ../ in template id must not escape generated_dir."""
    # Create a victim file outside the intended dir.
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    try:
        # Attempt traversal via slashed name segment.
        result = _find_template_file("con-../outside", tmp_path)
        assert result is None
    finally:
        outside.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# _parse_template_file
# ---------------------------------------------------------------------------


def test_parse_extracts_frontmatter_and_sections(tmp_path: Path) -> None:
    f = _write_template(
        tmp_path,
        "con-foo",
        body="Some content.",
        title="Foo Title",
        extra_frontmatter='tags: ["a", "b"]\n',
    )
    parsed = _parse_template_file(f)
    assert parsed["title"] == "Foo Title"
    assert parsed["name"] == "foo"
    assert parsed["subtype"] == "test"
    assert parsed["tags"] == ["a", "b"]
    assert "Some content." in parsed["sections"]["Overview"]


def test_parse_handles_string_tags(tmp_path: Path) -> None:
    f = _write_template(
        tmp_path,
        "con-bar",
        extra_frontmatter='tags: "x, y, z"\n',
    )
    parsed = _parse_template_file(f)
    assert parsed["tags"] == ["x", "y", "z"]


def test_parse_uses_filename_when_name_missing(tmp_path: Path) -> None:
    target = tmp_path / "concepts"
    target.mkdir(parents=True, exist_ok=True)
    f = target / "lonely.md"
    f.write_text("---\nsubtype: test\n---\n\n# Lonely\n", encoding="utf-8")
    parsed = _parse_template_file(f)
    assert parsed["name"] == "lonely"


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------


def test_parse_caches_by_mtime(tmp_path: Path) -> None:
    f = _write_template(tmp_path, "con-cached", body="v1")
    parsed_a = _parse_template_file(f)
    # Cache should now contain an entry for this file.
    assert any(str(f) == k[0] for k in _PARSED_TEMPLATE_CACHE.keys())
    # Parsing again returns the same object identity (cache hit).
    parsed_b = _parse_template_file(f)
    assert parsed_a is parsed_b


def test_parse_cache_invalidates_when_mtime_changes(tmp_path: Path) -> None:
    f = _write_template(tmp_path, "con-mutate", body="v1")
    first = _parse_template_file(f)
    assert "v1" in first["sections"]["Overview"]

    # Bump mtime by writing fresh content with a future timestamp.
    f.write_text(
        "---\nname: mutate\nsubtype: test\n---\n\n# T\n\n## Overview\n\nv2\n",
        encoding="utf-8",
    )
    future = time.time() + 5
    os.utime(f, (future, future))

    second = _parse_template_file(f)
    assert second is not first
    assert "v2" in second["sections"]["Overview"]


def test_invalidate_template_cache_clears_all(tmp_path: Path) -> None:
    f = _write_template(tmp_path, "con-x")
    _parse_template_file(f)
    assert _PARSED_TEMPLATE_CACHE
    invalidate_template_cache()
    assert not _PARSED_TEMPLATE_CACHE


def test_parse_handles_unreadable_path(tmp_path: Path) -> None:
    """When stat() fails, parser should fall through to the raw load path."""
    nonexistent = tmp_path / "ghost.md"
    with pytest.raises(FileNotFoundError):
        _parse_template_file(nonexistent)
