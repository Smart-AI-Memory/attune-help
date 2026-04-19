"""Schema + coverage guards for summaries_by_path.json (0.7.0).

Protects the path-keyed sidecar from drift:

- Every template path key resolves to a real .md file under
  templates/.
- Every summary is within category-specific length bounds.
- No duplicate summaries (copy-paste guard).
- Every feature in the feature-keyed summaries.json has at
  least one path-keyed summary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _PKG_ROOT / "src" / "attune_help" / "templates"
_PATH_SUMMARIES = _TEMPLATES_DIR / "summaries_by_path.json"
_FEATURE_SUMMARIES = _TEMPLATES_DIR / "summaries.json"

_PRIMARY = frozenset({"concepts", "quickstarts", "tasks", "references"})
_LESSON = frozenset({"errors", "warnings", "faqs"})

_PRIMARY_MIN, _PRIMARY_MAX = 80, 320
_LESSON_MIN, _LESSON_MAX = 40, 220
_NEUTRAL_MIN, _NEUTRAL_MAX = 60, 300


@pytest.fixture(scope="module")
def summaries_by_path() -> dict[str, str]:
    return json.loads(_PATH_SUMMARIES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def summaries_by_feature() -> dict[str, str]:
    return json.loads(_FEATURE_SUMMARIES.read_text(encoding="utf-8"))


def _bounds_for_category(category: str) -> tuple[int, int]:
    if category in _PRIMARY:
        return _PRIMARY_MIN, _PRIMARY_MAX
    if category in _LESSON:
        return _LESSON_MIN, _LESSON_MAX
    return _NEUTRAL_MIN, _NEUTRAL_MAX


def test_file_exists_and_is_valid_json():
    assert _PATH_SUMMARIES.is_file(), f"missing {_PATH_SUMMARIES}"
    data = json.loads(_PATH_SUMMARIES.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "top-level must be object"


def test_every_path_resolves_to_real_template(summaries_by_path):
    missing = [
        path_key for path_key in summaries_by_path if not (_TEMPLATES_DIR / path_key).is_file()
    ]
    assert (
        not missing
    ), "summaries_by_path.json references templates that don't exist:\n" + "\n".join(
        f"  - {p}" for p in missing
    )


def test_every_summary_is_non_empty_string(summaries_by_path):
    bad = [
        path
        for path, summary in summaries_by_path.items()
        if not isinstance(summary, str) or not summary.strip()
    ]
    assert not bad, f"empty or non-string summaries for: {bad}"


def test_no_newlines_in_summaries(summaries_by_path):
    bad = [p for p, s in summaries_by_path.items() if "\n" in s]
    assert not bad, f"summaries contain newlines: {bad}"


def test_no_duplicate_summaries(summaries_by_path):
    by_text: dict[str, str] = {}
    dupes: list[tuple[str, str]] = []
    for path, summary in summaries_by_path.items():
        if summary in by_text:
            dupes.append((path, by_text[summary]))
        else:
            by_text[summary] = path
    assert not dupes, "duplicate summaries (likely copy-paste):\n" + "\n".join(
        f"  - {a} == {b}" for a, b in dupes
    )


def test_summaries_respect_length_bounds(summaries_by_path):
    """Outer bounds — the polish pipeline has tighter inner bands;
    this test enforces the boundaries below which retrieval
    quality suffers.
    """
    violations: list[str] = []
    for path, summary in summaries_by_path.items():
        category = path.split("/", 1)[0] if "/" in path else ""
        lo, hi = _bounds_for_category(category)
        length = len(summary)
        if length < lo or length > hi:
            violations.append(f"{path} ({category}): {length} chars outside [{lo}, {hi}]")
    assert not violations, f"summaries outside length bounds ({len(violations)}):\n" + "\n".join(
        f"  - {v}" for v in violations[:10]
    )


def test_path_keys_have_md_extension(summaries_by_path):
    bad = [p for p in summaries_by_path if not p.endswith(".md")]
    assert not bad, f"path keys without .md suffix: {bad}"


def test_every_feature_has_path_coverage(summaries_by_path, summaries_by_feature):
    features = set(summaries_by_feature.keys())
    covered: set[str] = set()
    for path in summaries_by_path:
        stem = Path(path).stem.lower()
        for feature in features:
            if feature in stem:
                covered.add(feature)
    missing = features - covered
    assert not missing, "features with no path-keyed summary:\n" + "\n".join(
        f"  - {f}" for f in sorted(missing)
    )


def test_entry_count_is_reasonable(summaries_by_path):
    """Sanity check that the sidecar isn't empty or wildly wrong."""
    count = len(summaries_by_path)
    assert 80 <= count <= 400, f"unexpected entry count: {count}"
