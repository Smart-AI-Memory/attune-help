"""Benchmark every feature's fixture against the polished corpus.

Runs the full fixture suite and reports:

- Overall P@1 and R@3 across all features
- Per-feature P@1 and R@3 with hit/miss counts
- Features falling below a quality gate (default 60% P@1)

Uses the ``summaries_by_path.json`` sidecar (not the legacy
feature-keyed file) because that's the new 0.7.0 content.

Usage::

    uv run python scripts/benchmark_all_fixtures.py
    uv run python scripts/benchmark_all_fixtures.py --gate 0.7

Requires ``attune_rag`` + ``pyyaml`` installed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _REPO_ROOT / "src" / "attune_help" / "templates"
_FIXTURES_DIR = _TEMPLATES_DIR / "fixtures"


def _load_fixtures() -> list[dict]:
    fixtures = []
    for path in sorted(_FIXTURES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["_path"] = path
        fixtures.append(data)
    return fixtures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", type=float, default=0.60)
    parser.add_argument(
        "--summaries",
        default="summaries_by_path.json",
        help="Sidecar filename (default: summaries_by_path.json)",
    )
    args = parser.parse_args(argv)

    try:
        from attune_rag import DirectoryCorpus, KeywordRetriever, RagPipeline
    except ImportError:
        print("attune_rag not installed; run `uv pip install attune-rag`", file=sys.stderr)
        return 2

    corpus = DirectoryCorpus(
        root=_TEMPLATES_DIR,
        summaries_file=args.summaries,
        cross_links_file="cross_links.json",
    )
    pipeline = RagPipeline(corpus=corpus, retriever=KeywordRetriever())

    fixtures = _load_fixtures()
    total_queries = 0
    total_top1 = 0
    total_top3 = 0
    rows = []

    for fix in fixtures:
        feature = fix["feature"]
        expected = set(fix["expected_in_top_3"])
        queries = fix["queries"]
        top1 = 0
        top3 = 0
        misses = []
        for q in queries:
            result = pipeline.run(q, k=3)
            paths = [h.template_path for h in result.citation.hits]
            if paths and paths[0] in expected:
                top1 += 1
            if set(paths) & expected:
                top3 += 1
            else:
                misses.append((q, paths))
        total_queries += len(queries)
        total_top1 += top1
        total_top3 += top3
        rows.append(
            {
                "feature": feature,
                "total": len(queries),
                "top1": top1,
                "top3": top3,
                "p1": top1 / len(queries) if queries else 0.0,
                "r3": top3 / len(queries) if queries else 0.0,
                "misses": misses,
            }
        )

    print(f"Corpus:     {args.summaries}")
    print(
        f"Entries with summary: "
        f"{sum(1 for e in corpus.entries() if e.summary)}/"
        f"{sum(1 for _ in corpus.entries())}"
    )
    print(f"\nOverall P@1: {total_top1}/{total_queries} ({total_top1/total_queries:.1%})")
    print(f"Overall R@3: {total_top3}/{total_queries} ({total_top3/total_queries:.1%})")

    print("\nPer-feature breakdown:")
    print(f"  {'feature':<26} {'P@1':>8} {'R@3':>8}   misses")
    rows.sort(key=lambda r: r["p1"])
    below_gate = 0
    for r in rows:
        marker = " ✖" if r["p1"] < args.gate else "  "
        if r["p1"] < args.gate:
            below_gate += 1
        print(
            f"{marker}{r['feature']:<26} "
            f"{r['p1']:>7.1%} {r['r3']:>7.1%}   "
            f"{r['total']-r['top3']}/{r['total']}"
        )

    print(f"\nFeatures below {args.gate:.0%} P@1 gate: " f"{below_gate}/{len(rows)}")

    return 1 if below_gate > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
