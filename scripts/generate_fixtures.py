"""Generate per-feature RAG query fixtures via LLM.

Produces ``src/attune_help/templates/fixtures/{feature}.yaml``
files, each containing 25 natural-language queries a
developer would realistically ask when looking for that
feature. The fixtures have three jobs:

1. **Polish pipeline input.** Feed the queries as
   ``target_keywords`` into the summary polish prompt so
   the LLM encodes user vocabulary into summaries.
2. **Per-feature regression benchmark.** Protect retrieval
   quality from summary drift.
3. **Contrastive training data.** If attune-rag ever ships
   embeddings, these query→target pairs fine-tune the
   embedder.

Usage
-----

.. code-block:: bash

   # Dry-run for a single feature (no file written):
   uv run python scripts/generate_fixtures.py \\
       --features bug-predict --dry-run

   # Real run for a subset:
   uv run python scripts/generate_fixtures.py \\
       --features bug-predict,security-audit

   # All 26 features (requires ANTHROPIC_API_KEY):
   uv run python scripts/generate_fixtures.py

Requires ``ANTHROPIC_API_KEY`` and the ``anthropic`` SDK
installed in the active Python environment. Neither is a
runtime dep of attune-help — this is a dev-only generator
tool.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger("generate_fixtures")

# Fixtures live inside the shipped package so consumers
# (polish pipeline, benchmark suite, future attune-rag code)
# can read them from the installed distribution.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _REPO_ROOT / "src" / "attune_help" / "templates"
_FIXTURES_DIR = _TEMPLATES_DIR / "fixtures"
_SUMMARIES_FILE = _TEMPLATES_DIR / "summaries.json"

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 2000

_SYSTEM_PROMPT = """\
You write RAG query fixtures for the attune-help template library.

Each fixture is a set of 25 natural-language queries a developer
would realistically ask when looking for a specific feature's
documentation. The fixtures drive two things:

1. A keyword-based retriever that matches user queries against
   summaries + template content to surface the right feature doc.
2. An LLM polish pipeline that consumes these queries as
   ``target_keywords`` and encodes the vocabulary into each
   feature's polished summaries.

## Query categories (write 4-5 queries per category)

- **Literal** — direct use of the feature name or synonyms
  ("run bug predict", "bug prediction").
- **Pattern-specific** — queries about the concrete things the
  feature handles ("scan for dangerous eval calls", "find
  null reference bugs").
- **Intent-shape** — queries phrased around user intent
  ("what bugs can I catch before merging", "pre-merge
  quality gate").
- **Natural phrasing** — how users actually type, including
  colloquialisms ("sniff out hard-to-catch bugs").
- **Industry terminology** — domain-common synonyms users
  will use even if they don't appear in the template body
  ("CVE check" for security, "OWASP top 10 check",
  "pen test", "backdoor" for security; similar industry
  terms for other domains).
- **Edge / boundary** — queries at the boundary with
  adjacent features; acceptable if the query is ambiguous.

## Constraints

- Each query 2-8 words, lowercase, no trailing punctuation.
- No duplicates; no paraphrases that only differ by stopwords.
- Grounded in what the feature actually does — don't invent
  capabilities not described in the template body.
- Include industry vocabulary users genuinely say, even if
  those exact terms don't appear in the template body, as
  long as they're a real synonym for the feature's work.

## Output format

Return ONLY a YAML document (no surrounding text, no code
fence). Shape:

```yaml
version: 1
feature: {feature-name}
expected_in_top_3:
  - concepts/tool-{feature}.md
  - quickstarts/{skill-or-run}-{feature}.md
  - references/tool-{feature}.md
  - tasks/use-{feature}.md
queries:
  - "..."
  - "..."
  # ... exactly 25 queries total
```

The ``expected_in_top_3`` list includes every canonical
template path for this feature that the retriever should
accept as a correct hit. Paths you've been told about for
this feature ALL go in this list.
"""


def _load_feature_list() -> list[str]:
    data = json.loads(_SUMMARIES_FILE.read_text(encoding="utf-8"))
    return sorted(data.keys())


def _collect_template_paths(feature: str) -> list[str]:
    """Find every template file whose filename stem encodes this feature."""
    paths: list[str] = []
    patterns = (
        f"concepts/*{feature}*.md",
        f"quickstarts/*{feature}*.md",
        f"references/*{feature}*.md",
        f"tasks/*{feature}*.md",
        f"tips/*{feature}*.md",
    )
    for pattern in patterns:
        for path in sorted(_TEMPLATES_DIR.glob(pattern)):
            rel = path.relative_to(_TEMPLATES_DIR).as_posix()
            paths.append(rel)
    return paths


def _read_primary_body(feature: str) -> str:
    """Concept body is the strongest grounding signal for fixture generation."""
    candidates = (
        _TEMPLATES_DIR / "concepts" / f"tool-{feature}.md",
        _TEMPLATES_DIR / "concepts" / f"{feature}.md",
        _TEMPLATES_DIR / "quickstarts" / f"run-{feature}.md",
        _TEMPLATES_DIR / "quickstarts" / f"skill-{feature}.md",
    )
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return ""


def _user_prompt(feature: str, paths: list[str], body: str) -> str:
    body_excerpt = body[:3000] if body else "(no primary template body found)"
    return (
        f"Feature name: {feature}\n\n"
        f"Canonical template paths (include these in "
        f"expected_in_top_3):\n"
        + "\n".join(f"  - {p}" for p in paths)
        + f"\n\nFeature summary (from the feature-keyed "
        f"summaries.json):\n"
        f"  {_load_feature_summary(feature)!r}\n\n"
        f"Primary template body (use as the source of truth "
        f"for what the feature does):\n\n{body_excerpt}\n"
    )


def _load_feature_summary(feature: str) -> str:
    data = json.loads(_SUMMARIES_FILE.read_text(encoding="utf-8"))
    return data.get(feature, "")


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


_FENCE_RE = re.compile(r"^```(?:yaml)?\s*\n(.*?)\n```$", re.DOTALL | re.MULTILINE)


def _strip_fence(text: str) -> str:
    """Some models wrap YAML in code fences despite instructions."""
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _validate_fixture(raw_yaml: str, feature: str, expected_paths: list[str]) -> dict:
    import yaml

    data = yaml.safe_load(raw_yaml)
    if not isinstance(data, dict):
        raise ValueError(f"fixture for {feature!r} did not parse as a dict")
    for required in ("version", "feature", "expected_in_top_3", "queries"):
        if required not in data:
            raise ValueError(f"fixture for {feature!r} missing {required!r}")
    if data["feature"] != feature:
        raise ValueError(
            f"fixture feature {data['feature']!r} != requested {feature!r}",
        )
    queries = data["queries"]
    if not isinstance(queries, list):
        raise ValueError(f"fixture {feature!r} queries must be a list")
    if len(queries) < 20 or len(queries) > 30:
        raise ValueError(
            f"fixture {feature!r} expected ~25 queries, got {len(queries)}",
        )
    # Ensure at least one of the canonical paths is present.
    actual_expected = set(data["expected_in_top_3"])
    if not actual_expected & set(expected_paths):
        raise ValueError(
            f"fixture {feature!r} expected_in_top_3 doesn't intersect "
            f"the canonical paths found on disk ({expected_paths!r})",
        )
    # Dedup check — queries must be distinct.
    lowered = [q.lower().strip() for q in queries]
    if len(set(lowered)) != len(lowered):
        raise ValueError(f"fixture {feature!r} has duplicate queries")
    return data


def generate_for_feature(feature: str, model: str, dry_run: bool) -> dict:
    paths = _collect_template_paths(feature)
    if not paths:
        raise RuntimeError(f"no template files found for feature {feature!r}")
    body = _read_primary_body(feature)
    user = _user_prompt(feature, paths, body)
    logger.info("feature=%s calling model=%s", feature, model)
    raw = _call_llm(_SYSTEM_PROMPT, user, model)
    cleaned = _strip_fence(raw)
    fixture = _validate_fixture(cleaned, feature, paths)
    if dry_run:
        print(f"\n--- {feature} (dry run) ---")
        print(cleaned)
        return fixture
    _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _FIXTURES_DIR / f"{feature}.yaml"
    out_path.write_text(cleaned + "\n", encoding="utf-8")
    logger.info("feature=%s wrote %s", feature, out_path)
    return fixture


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_fixtures",
        description=__doc__.split("\n\n")[0] if __doc__ else "",
    )
    parser.add_argument(
        "--features",
        help="Comma-separated subset; default is all 26",
    )
    parser.add_argument("--model", default=_DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
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
    unknown = set(targets) - set(all_features)
    if unknown:
        print(f"Unknown features: {sorted(unknown)}", file=sys.stderr)
        return 2

    failed: list[tuple[str, str]] = []
    for feature in targets:
        try:
            generate_for_feature(feature, args.model, args.dry_run)
        except Exception as exc:  # noqa: BLE001
            logger.exception("feature=%s failed", feature)
            failed.append((feature, str(exc)))

    print(
        f"\nGenerated {len(targets) - len(failed)}/{len(targets)} "
        f"fixtures (model={args.model}, dry_run={args.dry_run})",
    )
    if failed:
        print("\nFailures:")
        for feature, err in failed:
            print(f"  {feature}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
