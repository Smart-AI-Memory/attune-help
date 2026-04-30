#!/usr/bin/env python3
"""
3-sweep validation harness for attune-help semantic freshness.

Sweep 1 — Parse integrity:  every .py file in the feature corpus parses cleanly.
Sweep 2 — Determinism:      compute_semantic_hash is identical on two consecutive calls.
Sweep 3 — HEAD vs HEAD^:    classify symbol changes as signature drift / body-only /
                             add / remove. Skipped if HEAD^ doesn't exist or git
                             is unavailable.

Usage:
    # Run against attune-ai (default)
    python scripts/validate_against_corpus.py

    # Point at any repo with a features.yaml
    python scripts/validate_against_corpus.py \\
        --repo /path/to/repo \\
        --manifest /path/to/repo/.help/features.yaml
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from attune_help.freshness.symbols import SymbolExtractor, SymbolRecord
from attune_help.manifest import load_manifest
from attune_help.staleness import _collect_matched_files, compute_semantic_hash

_EXTRACTOR = SymbolExtractor()

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Sweep1Result:
    total_files: int = 0
    parse_errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.parse_errors) == 0


@dataclass
class Sweep2Result:
    total_features: int = 0
    mismatches: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.mismatches) == 0


@dataclass
class Sweep3Result:
    signature_drifts: int = 0
    body_only_drifts: int = 0
    adds: int = 0
    removes: int = 0
    skipped_files: int = 0
    skipped_reason: str = ""

    @property
    def ok(self) -> bool:
        return self.signature_drifts == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_py_files(matched: list[str], root: Path) -> list[str]:
    return [p for p in matched if (root / p).suffix == ".py"]


def _git_show_prev(repo: Path, rel_path: str) -> str | None:
    """Return file content at HEAD^ or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD^:{rel_path}"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except FileNotFoundError:
        return None


def _symbols_from_source(source: str, path: Path) -> list[SymbolRecord]:
    try:
        # Write to tmp file so SymbolExtractor can read it
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            tmp = Path(f.name)
        records = _EXTRACTOR.extract(tmp)
        tmp.unlink(missing_ok=True)
        # Patch file field back to the real path for readability
        return [
            type(r)(
                **{k: (str(path) if k == "file" else v) for k, v in vars(r).items()}
            )
            for r in records
        ]
    except SyntaxError:
        return []


# ---------------------------------------------------------------------------
# Sweeps
# ---------------------------------------------------------------------------


def sweep1(py_files: list[tuple[str, Path]]) -> Sweep1Result:
    result = Sweep1Result(total_files=len(py_files))
    for rel, abs_path in py_files:
        try:
            source = abs_path.read_text(encoding="utf-8")
            ast.parse(source)
        except SyntaxError as e:
            result.parse_errors.append((rel, str(e)))
        except OSError as e:
            result.parse_errors.append((rel, f"OSError: {e}"))
    return result


def sweep2(features: dict, root: Path) -> Sweep2Result:
    result = Sweep2Result(total_features=len(features))
    for name, feat in features.items():
        h1, _ = compute_semantic_hash(feat, root)
        h2, _ = compute_semantic_hash(feat, root)
        if h1 != h2:
            result.mismatches.append(name)
    return result


def sweep3(py_files: list[tuple[str, Path]], repo: Path) -> Sweep3Result:
    result = Sweep3Result()

    # Check git availability first
    try:
        check = subprocess.run(
            ["git", "rev-parse", "HEAD^"],
            cwd=repo,
            capture_output=True,
        )
        if check.returncode != 0:
            result.skipped_reason = "HEAD^ does not exist (first commit or shallow clone)"
            return result
    except FileNotFoundError:
        result.skipped_reason = "git not available"
        return result

    for rel, abs_path in py_files:
        prev_source = _git_show_prev(repo, rel)
        if prev_source is None:
            result.skipped_files += 1
            continue

        current_records = {r.qualname: r for r in _EXTRACTOR.extract(abs_path)}
        prev_records = {r.qualname: r for r in _symbols_from_source(prev_source, abs_path)}

        all_qualnames = set(current_records) | set(prev_records)
        for qn in all_qualnames:
            if qn in current_records and qn not in prev_records:
                result.adds += 1
            elif qn not in current_records and qn in prev_records:
                result.removes += 1
            else:
                cur = current_records[qn]
                prv = prev_records[qn]
                if cur.signature_hash != prv.signature_hash:
                    result.signature_drifts += 1
                elif cur.body_hash != prv.body_hash:
                    result.body_only_drifts += 1

    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _print_report(
    s1: Sweep1Result,
    s2: Sweep2Result,
    s3: Sweep3Result,
    n_features: int,
    n_py: int,
) -> None:
    print()
    print("=" * 60)
    print("  attune-help semantic freshness — corpus validation")
    print("=" * 60)

    icon = lambda ok: "✔" if ok else "✖"  # noqa: E731

    print(f"\nSweep 1 — Parse integrity ({n_py} .py files across {n_features} features)")
    if s1.ok:
        print(f"  {icon(True)}  0 parse errors")
    else:
        print(f"  {icon(False)}  {len(s1.parse_errors)} parse error(s):")
        for path, msg in s1.parse_errors[:10]:
            print(f"       {path}: {msg}")

    print(f"\nSweep 2 — Determinism ({s2.total_features} features)")
    if s2.ok:
        print(f"  {icon(True)}  {s2.total_features}/{s2.total_features} hashes identical across two runs")
    else:
        print(f"  {icon(False)}  {len(s2.mismatches)} non-deterministic feature(s): {s2.mismatches}")

    print(f"\nSweep 3 — HEAD vs HEAD^")
    if s3.skipped_reason:
        print(f"  –  skipped: {s3.skipped_reason}")
    else:
        print(f"  {icon(s3.ok)}  signature drifts: {s3.signature_drifts}")
        print(f"       body-only drifts (correctly ignored): {s3.body_only_drifts}")
        print(f"       adds:    {s3.adds}")
        print(f"       removes: {s3.removes}")
        if s3.skipped_files:
            print(f"       new files (no HEAD^):  {s3.skipped_files}")

    all_ok = s1.ok and s2.ok and (s3.skipped_reason or s3.ok)
    print()
    print(f"  {'PASS' if all_ok else 'FAIL'} — sweeps complete")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_repo = Path(__file__).parent.parent.parent / "attune-ai"
    parser.add_argument(
        "--repo",
        type=Path,
        default=default_repo,
        help="Project root (default: ../attune-ai)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to features.yaml (default: <repo>/.help/features.yaml)",
    )
    args = parser.parse_args()

    repo: Path = args.repo.resolve()
    manifest_path: Path = args.manifest or (repo / ".help" / "features.yaml")

    if not manifest_path.exists():
        print(f"Error: manifest not found at {manifest_path}", file=sys.stderr)
        return 1

    print(f"Repo:     {repo}")
    print(f"Manifest: {manifest_path}")

    # load_manifest takes the directory containing features.yaml
    manifest = load_manifest(str(manifest_path.parent))
    features = manifest.features

    # Collect all matched files across all features
    all_py: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for feat in features.values():
        for rel in _collect_matched_files(feat, repo):
            abs_path = repo / rel
            if abs_path.suffix == ".py" and rel not in seen:
                seen.add(rel)
                all_py.append((rel, abs_path))

    print(f"Features: {len(features)}")
    print(f".py files: {len(all_py)}")

    s1 = sweep1(all_py)
    s2 = sweep2(features, repo)
    s3 = sweep3(all_py, repo)

    _print_report(s1, s2, s3, len(features), len(all_py))

    return 0 if (s1.ok and s2.ok) else 1


if __name__ == "__main__":
    sys.exit(main())
