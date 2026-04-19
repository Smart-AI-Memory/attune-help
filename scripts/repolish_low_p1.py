"""Repolish the bottom-N P@1 features and measure the delta.

Orchestrates a tight feedback loop over the features
that lag on retrieval quality:

1. Benchmark every fixture against the current
   ``summaries_by_path.json`` and capture per-feature
   P@1 / R@3.
2. Pick the N features with the lowest P@1 (default 6).
3. Back up the current sidecar so we can compare.
4. Invoke ``polish_summaries.py`` with
   ``--features <bottom-N>`` so only those features go
   through the LLM — differentiation hints in
   ``differentiation_hints.yaml`` are already applied by
   that script and give us the tighter per-feature
   framing.
5. Benchmark again.
6. Print a side-by-side delta table and return a
   non-zero exit if any targeted feature got worse.

Usage
-----

.. code-block:: bash

   # Default: bottom 6 features
   uv run python scripts/repolish_low_p1.py

   # Different cohort size
   uv run python scripts/repolish_low_p1.py --count 4

   # Dry-run: pick and report the cohort, no LLM calls
   uv run python scripts/repolish_low_p1.py --dry-run

   # Pass a cheaper model through to polish
   uv run python scripts/repolish_low_p1.py --model claude-haiku-4-5-20251001

Requires ``attune_rag``, ``pyyaml``, and the ``anthropic``
SDK (only for the polish phase). ``ANTHROPIC_API_KEY``
must be set unless ``--dry-run`` is used.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger("repolish_low_p1")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_TEMPLATES_DIR = _REPO_ROOT / "src" / "attune_help" / "templates"
_FIXTURES_DIR = _TEMPLATES_DIR / "fixtures"
_SUMMARIES_PATH_FILE = _TEMPLATES_DIR / "summaries_by_path.json"


@dataclass
class FeatureResult:
    feature: str
    total: int
    top1: int
    top3: int

    @property
    def p1(self) -> float:
        return self.top1 / self.total if self.total else 0.0

    @property
    def r3(self) -> float:
        return self.top3 / self.total if self.total else 0.0


def _load_fixtures() -> list[dict]:
    fixtures = []
    for path in sorted(_FIXTURES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        fixtures.append(data)
    return fixtures


def _run_benchmark(summaries_file: str) -> list[FeatureResult]:
    """Score every fixture against the given sidecar.

    Kept inline (rather than importing from
    ``benchmark_all_fixtures``) so this script is
    self-contained and can be called twice without
    fighting module-level caches.
    """
    try:
        from attune_rag import DirectoryCorpus, KeywordRetriever, RagPipeline
    except ImportError as exc:
        raise RuntimeError(
            "attune_rag not installed; run `uv pip install attune-rag`"
        ) from exc

    corpus = DirectoryCorpus(
        root=_TEMPLATES_DIR,
        summaries_file=summaries_file,
        cross_links_file="cross_links.json",
    )
    pipeline = RagPipeline(corpus=corpus, retriever=KeywordRetriever())

    results: list[FeatureResult] = []
    for fix in _load_fixtures():
        feature = fix["feature"]
        expected = set(fix["expected_in_top_3"])
        queries = fix["queries"]
        top1 = top3 = 0
        for q in queries:
            result = pipeline.run(q, k=3)
            paths = [h.template_path for h in result.citation.hits]
            if paths and paths[0] in expected:
                top1 += 1
            if set(paths) & expected:
                top3 += 1
        results.append(
            FeatureResult(
                feature=feature,
                total=len(queries),
                top1=top1,
                top3=top3,
            )
        )
    return results


def _pick_bottom(results: list[FeatureResult], count: int) -> list[FeatureResult]:
    """Lowest P@1 first; ties broken by lowest R@3 then name."""
    ordered = sorted(results, key=lambda r: (r.p1, r.r3, r.feature))
    return ordered[:count]


def _backup_sidecar() -> Path | None:
    if not _SUMMARIES_PATH_FILE.is_file():
        return None
    backup = _SUMMARIES_PATH_FILE.with_suffix(".json.pre-repolish.bak")
    shutil.copy2(_SUMMARIES_PATH_FILE, backup)
    return backup


def _run_polish(features: list[str], model: str, verbose: bool) -> int:
    cmd = [
        sys.executable,
        str(_SCRIPTS_DIR / "polish_summaries.py"),
        "--features",
        ",".join(features),
        "--model",
        model,
    ]
    if verbose:
        cmd.append("-v")
    logger.info("polish command: %s", " ".join(cmd))
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


def _render_delta_table(
    targeted: list[str],
    before: dict[str, FeatureResult],
    after: dict[str, FeatureResult],
) -> tuple[str, int]:
    """Return formatted table + number of regressions."""
    rows: list[str] = []
    rows.append(
        f"  {'feature':<28}"
        f" {'P@1 before':>11}"
        f" {'P@1 after':>10}"
        f" {'Δ':>7}"
        f" {'R@3 before':>11}"
        f" {'R@3 after':>10}"
        f" {'Δ':>7}"
    )
    rows.append("  " + "-" * 87)
    regressions = 0
    for feat in targeted:
        b = before[feat]
        a = after.get(feat)
        if a is None:
            rows.append(f"  {feat:<28}  (missing after benchmark)")
            continue
        dp = a.p1 - b.p1
        dr = a.r3 - b.r3
        if dp < 0:
            regressions += 1
        marker = " ✖" if dp < 0 else ("  " if dp == 0 else " ✔")
        rows.append(
            f"{marker}{feat:<28}"
            f" {b.p1:>10.1%}"
            f" {a.p1:>9.1%}"
            f" {dp:>+7.1%}"
            f" {b.r3:>10.1%}"
            f" {a.r3:>9.1%}"
            f" {dr:>+7.1%}"
        )
    return "\n".join(rows), regressions


def _overall(results: list[FeatureResult]) -> tuple[float, float, int, int, int]:
    total = sum(r.total for r in results)
    t1 = sum(r.top1 for r in results)
    t3 = sum(r.top3 for r in results)
    p1 = t1 / total if total else 0.0
    r3 = t3 / total if total else 0.0
    return p1, r3, total, t1, t3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repolish_low_p1",
        description=(
            "Re-polish the N lowest-P@1 features and report the delta."
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=6,
        help="How many of the lowest-P@1 features to repolish (default 6).",
    )
    parser.add_argument(
        "--features",
        help=(
            "Explicit comma-separated cohort (overrides --count). "
            "Use when you want to repolish a structurally related "
            "set together instead of the statistical bottom-N."
        ),
    )
    parser.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="Passed through to polish_summaries.py.",
    )
    parser.add_argument(
        "--summaries",
        default="summaries_by_path.json",
        help="Sidecar filename under templates/ (default: summaries_by_path.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pick and report the cohort, then stop — no LLM calls.",
    )
    parser.add_argument(
        "--regression-exit-code",
        type=int,
        default=2,
        help="Exit code when any targeted feature regresses (default 2).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    logger.info("benchmarking baseline corpus (%s)", args.summaries)
    baseline = _run_benchmark(args.summaries)
    before_map = {r.feature: r for r in baseline}

    if args.features:
        explicit = [f.strip() for f in args.features.split(",") if f.strip()]
        by_feature = {r.feature: r for r in baseline}
        unknown = [f for f in explicit if f not in by_feature]
        if unknown:
            logger.error("unknown features in --features: %s", unknown)
            return 1
        cohort = [by_feature[f] for f in explicit]
    else:
        cohort = _pick_bottom(baseline, args.count)
    if not cohort:
        logger.error("no fixtures found — nothing to repolish")
        return 1

    bp1, br3, btotal, bt1, bt3 = _overall(baseline)
    print(
        f"\nBaseline:    P@1={bp1:.1%} ({bt1}/{btotal})"
        f"  R@3={br3:.1%} ({bt3}/{btotal})"
    )
    header = (
        f"\nExplicit cohort ({len(cohort)} features):"
        if args.features
        else f"\nBottom {len(cohort)} features by P@1:"
    )
    print(header)
    for r in cohort:
        print(f"  {r.feature:<28}  P@1={r.p1:>6.1%}  R@3={r.r3:>6.1%}")

    if args.dry_run:
        print("\n(dry-run — no polish or re-benchmark)")
        return 0

    backup = _backup_sidecar()
    if backup:
        logger.info("sidecar backed up to %s", backup.name)

    target_features = [r.feature for r in cohort]
    rc = _run_polish(target_features, args.model, args.verbose)
    if rc != 0:
        logger.error("polish exited with code %d — aborting re-benchmark", rc)
        return rc

    logger.info("re-benchmarking after polish")
    after = _run_benchmark(args.summaries)
    after_map = {r.feature: r for r in after}

    table, regressions = _render_delta_table(target_features, before_map, after_map)
    print("\nPer-feature delta for targeted cohort:")
    print(table)

    ap1, ar3, atotal, at1, at3 = _overall(after)
    print(
        f"\nOverall:     "
        f"P@1 {bp1:.1%} → {ap1:.1%}  ({ap1-bp1:+.1%})"
        f"   R@3 {br3:.1%} → {ar3:.1%}  ({ar3-br3:+.1%})"
    )

    cohort_before = sum(before_map[f].top1 for f in target_features)
    cohort_after = sum(after_map[f].top1 for f in target_features if f in after_map)
    cohort_total = sum(before_map[f].total for f in target_features)
    cohort_bp1 = cohort_before / cohort_total if cohort_total else 0.0
    cohort_ap1 = cohort_after / cohort_total if cohort_total else 0.0
    print(
        f"Cohort-only: "
        f"P@1 {cohort_bp1:.1%} → {cohort_ap1:.1%}"
        f"  ({cohort_ap1-cohort_bp1:+.1%})"
    )

    if regressions:
        print(
            f"\n⚠ {regressions}/{len(target_features)} targeted features regressed."
        )
        if backup:
            print(f"  Restore with:  cp {backup} {_SUMMARIES_PATH_FILE}")
        return args.regression_exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
