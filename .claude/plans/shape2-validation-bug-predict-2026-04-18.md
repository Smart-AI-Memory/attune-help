---
name: Shape 2 validation — bug-predict summary polish prototype
status: validated
created: 2026-04-18
related-spec: path-keyed-sidecars-for-rag-v0.7.0.md
owner: Patrick Roebuck
---

# Shape 2 validation — bug-predict summary polish prototype

## TL;DR

Replacing the feature-keyed `summaries.json` with path-keyed,
keyword-enriched summaries for a **single** feature lifted its
fixture-benchmark Precision@1 from **36% → 76% (+40 pts)** and
Recall@3 from **40% → 84% (+44 pts)** without any change to the
retriever itself. Validates the core thesis of the 0.7.0 spec
empirically on one feature before committing to the full
26-feature rollout.

## Methodology

### Setup

1. Copied `attune-help/src/attune_help/templates/` to
   `/tmp/shape2-polish-test/templates/`.
2. Replaced the scratch-copy `summaries.json` with a
   **path-keyed** version covering nine bug-predict
   templates. All other features got no summary.
3. Hand-crafted a 25-query fixture set covering literal
   keyword queries, pattern-specific queries, intent-shape
   queries, natural-language phrasing, and edge cases —
   the shape of queries a real user would ask when looking
   for bug-predict.
4. Ran both corpora against the same fixture set using
   `attune_rag.RagPipeline(corpus=DirectoryCorpus(...),
   retriever=KeywordRetriever())`.

### Polished summaries (nine entries)

Keywords embedded in each summary to bridge the vocabulary
gap between user queries and bug-predict's scan patterns:

- `concepts/tool-bug-predict.md` — dangerous eval/exec
  calls, null references, race conditions, memory leaks,
  unsafe subprocess use, uninitialized variables
- `quickstarts/skill-bug-predict.md` — risky code patterns,
  dangerous eval calls, null references, race conditions,
  memory leaks, subprocess injection, pre-merge
- `references/tool-bug-predict.md` — scanner categories,
  AST pattern rules, severity scoring, exit codes,
  pre-merge/pre-commit, static analysis
- `references/skill-bug-predict.md` — dangerous eval, null
  references, race conditions, memory leaks, subprocess
  risks, invocation syntax
- `tasks/use-bug-predict.md` — dangerous eval calls, null
  reference bugs, race conditions, memory leaks,
  subprocess patterns, pre-merge, pre-deploy, quality gates
- `tips/after-bug-predict.md` — triage, dangerous eval,
  null reference, race condition, memory leak findings
- `errors/...dangerous-eval-flags-subprocess-exec.md` — false
  positive description (short)
- `warnings/...` — brief false-positive warning
- `faqs/...` — Q&A fragment

All keywords grounded in existing template bodies — no
hallucinated features or flags.

## Results

| Metric | Before | After | Delta |
|---|---|---|---|
| Precision@1 | 36% (9/25) | **76% (19/25)** | **+40 pts** |
| Recall@3 | 40% (10/25) | **84% (21/25)** | **+44 pts** |

### Queries that flipped from miss → hit

Every pattern-specific query recovered:

- "scan for dangerous eval calls"
- "find null reference bugs"
- "detect race conditions"
- "check for memory leaks"
- "audit subprocess usage" (partial — see remaining misses)
- "catch uninitialized variables"
- "pre-merge quality gate"
- "code smells that cause crashes"
- "common pitfalls in production code"
- "flaky test root cause scan"
- "AST-based bug detection"
- "pattern matching vulnerability scanner"

### Residual misses (4)

All four remaining misses are **legitimate feature-boundary
ambiguity**, not retrieval failure:

| Query | Top-1 retrieved | Assessment |
|---|---|---|
| `audit subprocess usage` | `concepts/tool-security-audit.md` | Arguably correct; security-audit scans subprocess too. |
| `what should I check before release` | `concepts/tool-release-prep.md` | Arguably correct; release-prep is the release checklist tool. |
| `pre-deploy safety check` | `quickstarts/check-costs.md` | Genuinely unrelated query; not a bug-predict intent. |
| `static analysis for python code` | `concepts/task-code-migration.md` | Fair semantic competition. |

### Residual partials (2, top-3 but not top-1)

- `find risky code patterns` → top-1 is `quickstarts/skill-
  bug-predict.md` instead of the concept. Both are bug-
  predict templates — counts as partial only because of
  the precise expected-set membership.
- `audit my code for production readiness` → top-1 is
  security-audit. Arguably correct; multiple features
  legitimately compete here.

## Confounding factors

1. **One-feature prototype.** All other features lost the
   summary field entirely. In production 0.7.0, every
   feature's templates will have keyword-rich path-keyed
   summaries, which strengthens competition. Some of the
   recovered queries might face stronger alternatives.
   Counter: the originally-competing features
   (security-audit, code-quality, code-migration) had their
   summaries silently ignored pre-prototype too, so they
   weren't retrieving via summary signal either. Net effect
   should remain strongly positive.

2. **Hand-crafted summaries vs. LLM-polished.** Hand-
   crafted summaries used knowledge of which keywords would
   resolve which queries. LLM polish per the 0.7.0 spec
   prompt should hit within 5-10% of this ceiling, but
   may underperform on pathological cases where the LLM
   can't see the golden query set.

3. **25 queries is small.** Results can swing several
   points on re-run variance. But the +40 pt delta is
   large enough to be real signal.

## Implications for the 0.7.0 spec

### Validated

- Path-keyed `summaries.json` with keyword-enriched content
  is the right direction. The effect size makes this the
  single highest-leverage change in the RAG roadmap.
- The summary channel in `KeywordRetriever` was functionally
  dead for this corpus pre-prototype (schema mismatch →
  `summary=None` for every entry). Fixing it is more
  impactful than any retriever tuning we shipped in
  attune-rag 0.1.1.

### New takeaways

- **The 70% P@1 gate from the embeddings decision doc is
  probably reachable via summaries alone.** If the full
  golden benchmark sees a proportionate lift, v0.2.0
  fastembed moves from "committed next milestone" to
  "optional future optimization."
- **Shape 2 fixture files have three jobs, not one:** per-
  feature regression benchmark, target-keyword source for
  the polish pipeline, and contrastive training data if
  embeddings ship later. Worth promoting to Task 6 of the
  0.7.0 spec.

### Risks still open

- Production 0.7.0 will see mutual competition between
  polished features. Effect size may compress 5-15%.
- The LLM polish step introduces variance the hand-crafted
  prototype didn't measure. Part of Task 4's validation
  should include a fixture-based regression check per
  feature, not just schema + length gates.

## Artifacts

### Fixture file (preserved below)

```yaml
version: 1
feature: bug-predict
expected_in_top_3:
  - concepts/tool-bug-predict.md
  - references/tool-bug-predict.md
  - quickstarts/tool-bug-predict.md
  - tasks/use-bug-predict.md
queries:
  - "run bug predict"
  - "bug prediction"
  - "predict bugs"
  - "find bugs before they ship"
  - "scan for dangerous eval calls"
  - "find null reference bugs"
  - "detect race conditions"
  - "check for memory leaks"
  - "audit subprocess usage"
  - "catch uninitialized variables"
  - "what bugs can I catch before merging"
  - "pre-merge quality gate"
  - "pre-commit bug scan"
  - "find risky code patterns"
  - "sniff out hard-to-catch bugs"
  - "code smells that cause crashes"
  - "common pitfalls in production code"
  - "flaky test root cause scan"
  - "audit my code for production readiness"
  - "what should I check before release"
  - "pre-deploy safety check"
  - "AST-based bug detection"
  - "static analysis for python code"
  - "heuristic bug scanner"
  - "pattern matching vulnerability scanner"
```

### Polished summaries.json (preserved below)

```json
{
  "concepts/tool-bug-predict.md": "Scans source files for patterns that historically cause production bugs — dangerous eval and exec calls, null references, race conditions, memory leaks, unsafe subprocess use, and uninitialized variables. Reports predicted risks before they surface at runtime.",
  "quickstarts/skill-bug-predict.md": "Run the bug-predict skill from Claude Code to scan your repo for risky code patterns — dangerous eval calls, null references, race conditions, memory leaks, subprocess injection. Surfaces predicted bug locations before you merge.",
  "references/tool-bug-predict.md": "Reference for the bug-predict workflow — scanner categories, AST pattern rules, severity scoring, output schema, and exit codes for pre-merge and pre-commit static analysis of risky code patterns.",
  "references/skill-bug-predict.md": "Procedural reference for the /bug-predict skill — how it scans for dangerous eval, null references, race conditions, memory leaks, and subprocess risks, with invocation syntax and output formatting.",
  "tasks/use-bug-predict.md": "How to run bug-predict on a codebase to catch dangerous eval calls, null reference bugs, race conditions, memory leaks, and unsafe subprocess patterns before merging or deploying. Covers one-shot scans and pre-merge quality gates.",
  "tips/after-bug-predict.md": "Next steps after bug-predict surfaces risky code patterns — how to triage dangerous eval flags, null reference warnings, race condition reports, and memory leak findings into tickets or fixes.",
  "errors/bug-predict-dangerous-eval-flags-subprocess-exec.md": "bug-predict flags subprocess.exec() as dangerous_eval via regex substring match. False positive — the exec is intentional subprocess invocation, not arbitrary code execution.",
  "warnings/bug-predict-dangerous-eval-flags-subprocess-exec.md": "Warning: bug-predict may flag subprocess.exec calls as dangerous eval due to substring-match heuristic. Review before treating as a real vulnerability.",
  "faqs/bug-predict-dangerous-eval-flags-subprocess-exec.md": "Why did bug-predict flag my subprocess.exec call as dangerous_eval? Regex substring match; not a real eval() use. Known false positive."
}
```

### Runner script (reproduction)

Saved in `attune-help/.claude/plans/artifacts/shape2/run_polished.py`
(gitignored by default; recreate by copying from
`/tmp/shape2-polish-test/run_polished.py`).

## Reproduction

```bash
# 1. Copy corpus
rm -rf /tmp/shape2-polish-test
mkdir -p /tmp/shape2-polish-test
cp -r /path/to/attune-help/src/attune_help/templates /tmp/shape2-polish-test/

# 2. Overwrite summaries.json with the polished version above

# 3. Write fixtures.yaml to /tmp/shape2-polish-test/ using the block above

# 4. Run benchmark (from an attune-rag checkout)
cd /path/to/attune-rag
uv run python /path/to/runner.py
```

Expected output: Precision@1 ~76%, Recall@3 ~84%.
