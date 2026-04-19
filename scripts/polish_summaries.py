"""LLM polish pass: produce path-keyed keyword-rich summaries.

Reads every .md template under
``src/attune_help/templates/``, rewrites each one's summary
via Claude so the result is:

- Path-keyed (not feature-keyed) so attune-rag's
  ``DirectoryCorpus`` can actually use the signal.
- Keyword-enriched using the fixture queries as
  ``target_keywords``.
- Length-bounded: 180-280 chars for primary categories,
  60-150 chars for lesson-style (errors/warnings/faqs).
- Declarative voice and grounded in the template body.

Output lands in
``src/attune_help/templates/summaries_by_path.json``. The
existing feature-keyed ``summaries.json`` is left
untouched for backwards compatibility.

Usage
-----

.. code-block:: bash

   # Dry-run one feature (prints polished summaries):
   uv run python scripts/polish_summaries.py \\
       --features bug-predict --dry-run

   # Polish a subset of features:
   uv run python scripts/polish_summaries.py \\
       --features bug-predict,security-audit

   # Full run (all templates whose feature has a fixture):
   uv run python scripts/polish_summaries.py

Requires ``ANTHROPIC_API_KEY`` and the ``anthropic`` SDK
installed in the active Python environment. Dev-only
generator — not a runtime dep of attune-help.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger("polish_summaries")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _REPO_ROOT / "src" / "attune_help" / "templates"
_FIXTURES_DIR = _TEMPLATES_DIR / "fixtures"
_SUMMARIES_FEATURE_FILE = _TEMPLATES_DIR / "summaries.json"
_SUMMARIES_PATH_FILE = _TEMPLATES_DIR / "summaries_by_path.json"
_DIFF_HINTS_FILE = _REPO_ROOT / "scripts" / "differentiation_hints.yaml"

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 400
_BODY_CHAR_LIMIT = 2500

_PRIMARY_CATEGORIES = frozenset({"concepts", "quickstarts", "tasks", "references"})
_LESSON_CATEGORIES = frozenset({"errors", "warnings", "faqs"})
_NEUTRAL_CATEGORIES = frozenset({"tips", "notes", "troubleshooting", "comparisons"})

_PRIMARY_MIN, _PRIMARY_MAX = 180, 280
_LESSON_MIN, _LESSON_MAX = 60, 200
_NEUTRAL_MIN, _NEUTRAL_MAX = 120, 240


_SYSTEM_PROMPT = """\
You are writing a one-line summary for a developer-documentation
template in the attune-help library. These summaries feed a
keyword-based RAG retriever: developers ask questions in natural
language, and the retriever ranks templates by how well their
summaries overlap with the query. So the summary needs to be
keyword-dense AND grammatical — for the retriever AND for a
human scanning the help system.

## Constraints

- Length: stay within the character range the request specifies.
  Below the minimum is thin; above the maximum fails the schema.
- Voice: declarative, not imperative. "Scans source files for …"
  not "Scan your source files for …".
- Grounding: every domain-specific term you use must appear in
  or be clearly implied by the provided template_body, EXCEPT
  for industry-common synonyms listed below.
- Industry terminology: include domain-common industry terms
  users genuinely say when searching for this kind of feature —
  CVE, OWASP, pen test, backdoor for security; cyclomatic
  complexity, static analysis for bug analysis; REST, CRUD,
  pagination for API work; Alembic, migration, rollback for
  databases; etc. — even if those exact terms don't appear in
  the template body, as long as they're a real synonym for what
  the template describes.
- Idempotency: if the current summary already meets the
  constraints, return it with minimal edits.

## Category-specific shape

- concepts/ — WHAT the feature is and which concrete patterns
  or situations it addresses. 3-5 noun-phrase keywords.
- quickstarts/ — the OUTCOME after following the steps.
  Action verbs + target objects.
- references/ — WHAT is documented (CLI flags, API surface,
  output format, exit codes). Technical terms users would look
  up.
- tasks/ — the TASK accomplished. The domain of the task.
- tips/ / notes/ / troubleshooting/ — guidance; medium length.
- errors/ / warnings/ / faqs/ — brief one-liner describing the
  symptom or question. Do NOT pad: these categories are
  penalized in the retriever and long summaries actively hurt
  ranking.

## Output format

Return ONLY the summary text. No quotes, no markdown, no
"Summary:" prefix, no trailing whitespace.
"""


def _load_feature_list() -> list[str]:
    data = json.loads(_SUMMARIES_FEATURE_FILE.read_text(encoding="utf-8"))
    return sorted(data.keys())


def _load_fixture_keywords(feature: str) -> list[str]:
    """Extract every distinct token used in the fixture queries."""
    import yaml

    path = _FIXTURES_DIR / f"{feature}.yaml"
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    queries = data.get("queries", [])
    # Keep the queries themselves as "target phrases" — the LLM
    # will pick out the valuable tokens/phrases more organically
    # than if we hand it a bag of words.
    return list(queries)


def _load_feature_summary(feature: str) -> str:
    data = json.loads(_SUMMARIES_FEATURE_FILE.read_text(encoding="utf-8"))
    return data.get(feature, "")


def _load_diff_hint(feature: str) -> dict | None:
    """Return {'hint': str, 'not': [str]} or None if the feature has no hint."""
    if not _DIFF_HINTS_FILE.is_file():
        return None
    import yaml

    data = yaml.safe_load(_DIFF_HINTS_FILE.read_text(encoding="utf-8"))
    return data.get(feature)


def _infer_category(path: Path) -> str:
    rel = path.relative_to(_TEMPLATES_DIR)
    parts = rel.parts
    if len(parts) <= 1:
        return ""
    return parts[0]


def _infer_feature_from_path(path: Path, known_features: list[str]) -> str | None:
    """Match a template path to one of the known features via stem."""
    stem = path.stem.lower()
    for feature in known_features:
        if feature in stem:
            return feature
    return None


def _length_bounds(category: str) -> tuple[int, int]:
    if category in _PRIMARY_CATEGORIES:
        return _PRIMARY_MIN, _PRIMARY_MAX
    if category in _LESSON_CATEGORIES:
        return _LESSON_MIN, _LESSON_MAX
    return _NEUTRAL_MIN, _NEUTRAL_MAX


def _user_prompt(
    *,
    path_rel: str,
    category: str,
    feature: str,
    feature_summary: str,
    fixture_queries: list[str],
    diff_hint: dict | None,
    body: str,
    min_chars: int,
    max_chars: int,
) -> str:
    body_excerpt = body[:_BODY_CHAR_LIMIT] if body else "(template body not available)"
    fixture_block = (
        "Fixture queries (these are the natural-language questions "
        "users will ask for this feature — include their vocabulary "
        "naturally in the summary):\n" + "\n".join(f"  - {q}" for q in fixture_queries)
        if fixture_queries
        else "Fixture queries: (none — derive keywords from the body)"
    )

    if diff_hint:
        not_list = diff_hint.get("not") or []
        diff_block = (
            "\n\nFeature differentiation — what makes THIS feature "
            "unique vs. adjacent features that share vocabulary:\n"
            f"  {diff_hint['hint'].strip()}\n"
        )
        if not_list:
            diff_block += (
                "  Distinguishes from: "
                + ", ".join(sorted(not_list))
                + " — the summary should emphasize what this "
                "feature does that those don't.\n"
            )
    else:
        diff_block = ""

    return (
        f"Template path: {path_rel}\n"
        f"Category: {category}\n"
        f"Feature: {feature}\n"
        f"Length range: {min_chars}-{max_chars} characters\n"
        f"Existing feature-keyed summary (for reference only — "
        f"don't just copy it): {feature_summary!r}\n\n"
        f"{fixture_block}"
        f"{diff_block}\n\n"
        f"Template body:\n\n{body_excerpt}"
    )


def _call_llm(system: str, user: str, model: str) -> str:
    try:
        import anthropic  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "anthropic SDK not installed; run `pip install anthropic`",
        ) from exc

    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
    response = client.messages.create(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    blocks = [b.text for b in response.content if hasattr(b, "text")]
    return "".join(blocks).strip()


_QUOTE_STRIP_RE = re.compile(r'^["\']|["\']$')


def _post_process(text: str) -> str:
    text = text.strip()
    # Strip wrapping quotes if the model ignored the "no quotes"
    # rule.
    while _QUOTE_STRIP_RE.search(text):
        text = _QUOTE_STRIP_RE.sub("", text).strip()
    # Strip "Summary:" prefix if present.
    if text.lower().startswith("summary:"):
        text = text.split(":", 1)[1].strip()
    return text


def _validate(summary: str, min_chars: int, max_chars: int) -> list[str]:
    issues: list[str] = []
    if len(summary) < min_chars:
        issues.append(f"length {len(summary)} < min {min_chars}")
    if len(summary) > max_chars:
        issues.append(f"length {len(summary)} > max {max_chars}")
    if summary.count("\n") > 0:
        issues.append("contains newlines")
    return issues


def _polish_one(
    path: Path,
    features: list[str],
    model: str,
    use_diff_hints: bool,
) -> tuple[str, list[str]]:
    rel = path.relative_to(_TEMPLATES_DIR).as_posix()
    category = _infer_category(path)
    feature = _infer_feature_from_path(path, features) or ""
    feature_summary = _load_feature_summary(feature) if feature else ""
    fixture_queries = _load_fixture_keywords(feature) if feature else []
    diff_hint = _load_diff_hint(feature) if (feature and use_diff_hints) else None
    min_chars, max_chars = _length_bounds(category)
    body = path.read_text(encoding="utf-8")

    user = _user_prompt(
        path_rel=rel,
        category=category,
        feature=feature or "(unknown)",
        feature_summary=feature_summary,
        fixture_queries=fixture_queries,
        diff_hint=diff_hint,
        body=body,
        min_chars=min_chars,
        max_chars=max_chars,
    )
    raw = _call_llm(_SYSTEM_PROMPT, user, model)
    summary = _post_process(raw)
    issues = _validate(summary, min_chars, max_chars)
    return summary, issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="polish_summaries",
        description=__doc__.split("\n\n")[0] if __doc__ else "",
    )
    parser.add_argument(
        "--features",
        help="Comma-separated subset; default is every feature with a fixture",
    )
    parser.add_argument("--model", default=_DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Cap total templates polished this run (useful for testing)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--no-diff-hints",
        action="store_true",
        help="Disable feature-differentiation hints (default on)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    all_features = _load_feature_list()
    targets = (
        [f.strip() for f in args.features.split(",") if f.strip()]
        if args.features
        else all_features
    )

    # Collect candidate template paths — every .md file under
    # templates/ whose feature is in `targets`.
    candidates: list[Path] = []
    for md in sorted(_TEMPLATES_DIR.rglob("*.md")):
        if "fixtures" in md.parts:
            continue
        feature = _infer_feature_from_path(md, all_features)
        if feature is None or feature not in targets:
            continue
        candidates.append(md)

    if args.limit > 0:
        candidates = candidates[: args.limit]

    logger.info("polishing %d templates across %d features", len(candidates), len(targets))

    # Load existing summaries_by_path.json to preserve unaffected
    # entries (idempotent incremental runs).
    existing: dict[str, str] = {}
    if _SUMMARIES_PATH_FILE.is_file():
        existing = json.loads(_SUMMARIES_PATH_FILE.read_text(encoding="utf-8"))

    polished: dict[str, str] = dict(existing)
    issues_report: list[tuple[str, list[str]]] = []
    for md in candidates:
        rel = md.relative_to(_TEMPLATES_DIR).as_posix()
        try:
            summary, issues = _polish_one(
                md, all_features, args.model, use_diff_hints=not args.no_diff_hints
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("failed to polish %s", rel)
            issues_report.append((rel, [f"error: {exc}"]))
            continue
        if issues:
            issues_report.append((rel, issues))
        polished[rel] = summary
        logger.info("polished %s (%d chars)", rel, len(summary))
        if args.dry_run:
            print(f"\n--- {rel} ---\n{summary}")

    if not args.dry_run:
        _SUMMARIES_PATH_FILE.write_text(
            json.dumps(polished, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        logger.info("wrote %d entries to %s", len(polished), _SUMMARIES_PATH_FILE)

    if issues_report:
        print("\nValidation issues / failures:")
        for rel, issues in issues_report:
            print(f"  {rel}:")
            for issue in issues:
                print(f"    - {issue}")
        return 1 if any("error:" in i for _, issues in issues_report for i in issues) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
