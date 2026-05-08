"""Tests for the template-id prefix maps.

attune-help resolves a `{prefix}-{slug}` template id to a file via
``templates._PREFIX_MAP`` (used by ``_find_template_file``) and
``progression._COMPOUND_PREFIXES`` (used by retrieval ranking).

These two maps must stay in sync with each other AND with the
template-type enum in ``attune-rag/src/attune_rag/editor/template_schema.json``
— the schema is the source of truth for which template kinds exist.
The schema can't be imported here without making attune-rag a
dependency (which would violate ADR-002), so we hard-code the
expected set with a comment pointing at the source. Update this list
in lockstep with the schema enum.
"""

from __future__ import annotations

from attune_help.progression import _COMPOUND_PREFIXES
from attune_help.templates import _PREFIX_MAP

# Mirror of `attune-rag/src/attune_rag/editor/template_schema.json`
# `properties.type.enum`. If the enum changes there, change this list
# AND add the matching prefix below.
_EXPECTED_KINDS = {
    "comparison",
    "concept",
    "error",
    "faq",
    "guide",
    "note",
    "quickstart",
    "reference",
    "task",
    "tip",
    "troubleshooting",
    "warning",
}

# Expected mapping: kind → (prefix, directory). Only the prefix and
# directory live in code; the kind is what the schema declares.
_EXPECTED_PREFIXES: dict[str, tuple[str, str]] = {
    "comparison": ("com", "comparisons"),
    "concept": ("con", "concepts"),
    "error": ("err", "errors"),
    "faq": ("faq", "faqs"),
    "guide": ("gui", "guides"),
    "note": ("not", "notes"),
    "quickstart": ("qui", "quickstarts"),
    "reference": ("ref", "references"),
    "task": ("tas", "tasks"),
    "tip": ("tip", "tips"),
    "troubleshooting": ("tro", "troubleshooting"),
    "warning": ("war", "warnings"),
}


def test_prefix_map_covers_every_schema_kind() -> None:
    """Every kind in the schema enum has a prefix → dir mapping."""
    assert set(_EXPECTED_PREFIXES.keys()) == _EXPECTED_KINDS

    actual = dict(_PREFIX_MAP)
    expected = {prefix: directory for prefix, directory in _EXPECTED_PREFIXES.values()}
    assert actual == expected, (
        f"_PREFIX_MAP drift — missing prefixes={set(expected) - set(actual)}, "
        f"extra prefixes={set(actual) - set(expected)}"
    )


def test_compound_prefixes_include_every_base_prefix() -> None:
    """Every prefix in _PREFIX_MAP is reachable in retrieval ranking.

    `_COMPOUND_PREFIXES` is ordered longest-first; we only check
    presence, not exact order — order is locked by other tests in
    test_progression.
    """
    base_prefixes = {f"{p}-" for p in _PREFIX_MAP}
    compound_set = set(_COMPOUND_PREFIXES)
    missing = base_prefixes - compound_set
    assert not missing, f"_COMPOUND_PREFIXES is missing base prefixes: {missing}"


def test_quickstart_resolves_to_qui_prefix() -> None:
    """Pin: ``quickstart`` → ``qui-`` (not ``qst-`` or anything else)."""
    assert _PREFIX_MAP.get("qui") == "quickstarts"
    assert "qui-" in _COMPOUND_PREFIXES


def test_guide_resolves_to_gui_prefix() -> None:
    """Pin: ``guide`` → ``gui-``.

    Added when the schema enum was reconciled with the corpus
    (attune-rag commit 06ebcec). No template uses ``type: guide`` yet
    in the corpus, but the cross-linker would silently drop any new
    one without this mapping.
    """
    assert _PREFIX_MAP.get("gui") == "guides"
    assert "gui-" in _COMPOUND_PREFIXES
