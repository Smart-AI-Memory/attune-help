"""Show the actual misses for each low-P@1 feature.

Prints the query, the expected paths, and which features the
retriever returned instead. Used to hand-craft per-feature
differentiation prompts that target the right competitors.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _REPO_ROOT / "src" / "attune_help" / "templates"
_FIXTURES_DIR = _TEMPLATES_DIR / "fixtures"

_LOW_P1 = [
    "spec",
    "code-quality",
    "planning",
    "refactor-plan",
    "workflow-orchestration",
    "security-audit",
]


def _feature_of(path: str, features: list[str]) -> str:
    stem = path.rsplit("/", 1)[-1].replace(".md", "").lower()
    # Sort by length descending so longer feature names win.
    for f in sorted(features, key=len, reverse=True):
        if f in stem:
            return f
    return "?"


def main() -> int:
    from attune_rag import DirectoryCorpus, KeywordRetriever, RagPipeline

    corpus = DirectoryCorpus(
        root=_TEMPLATES_DIR,
        summaries_file="summaries_by_path.json",
        cross_links_file="cross_links.json",
    )
    pipeline = RagPipeline(corpus=corpus, retriever=KeywordRetriever())

    all_features = sorted(p.stem for p in _FIXTURES_DIR.glob("*.yaml"))

    for feat in _LOW_P1:
        fix = yaml.safe_load((_FIXTURES_DIR / f"{feat}.yaml").read_text(encoding="utf-8"))
        expected = set(fix["expected_in_top_3"])
        queries = fix["queries"]
        print(f"\n=== {feat} ===")
        for q in queries:
            result = pipeline.run(q, k=3)
            paths = [h.template_path for h in result.citation.hits]
            if paths and paths[0] in expected:
                continue  # P@1 hit
            competitors = [_feature_of(p, all_features) for p in paths]
            print(f"  Q: {q}")
            print(f"    returned: {competitors[:3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
