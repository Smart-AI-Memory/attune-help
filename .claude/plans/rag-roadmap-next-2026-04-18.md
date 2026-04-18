---
name: RAG roadmap — next 5 moves after the Shape 2 validation
status: draft
created: 2026-04-18
related:
  - path-keyed-sidecars-for-rag-v0.7.0.md
  - shape2-validation-bug-predict-2026-04-18.md
  - attune-ai/docs/rag/embeddings-decision-2026-04-17.md
owner: Patrick Roebuck
---

# RAG roadmap — next 5 moves after the Shape 2 validation

## Context

Two data points now exist where previously there was only
speculation:

| Feature | P@1 before | P@1 after | Delta |
|---|---|---|---|
| bug-predict | 36% | 76% | +40 pts |
| security-audit | — | 72% | — |

These are single-feature fixture benchmarks with hand-
crafted keyword-rich path-keyed summaries. Residual misses
in both cases are feature-boundary ambiguities (cross-
routing between `bug-predict` and `security-audit`,
`security-audit` and `code-quality`, etc.) rather than
retrieval failures.

The full RAG retrieval improvement path now has one
unambiguously highest-leverage move (path-keyed
summaries) and four supporting moves. This doc captures
all five as concrete specs with owners, sequencing,
and decision criteria.

## Why this doc exists

Without a consolidated view, each of the five moves would
be negotiated separately, risking:

- Inconsistent sequencing (e.g. rerunning the golden
  benchmark before 0.7.0 content ships → wasted run)
- The fastembed v0.2.0 track continuing by inertia when
  the data now suggests it's optional
- Shape 2 fixtures existing as one-off scripts instead of
  a durable per-feature artifact
- The "summary channel was dead weight" lesson remaining
  in session memory instead of CLAUDE.md

Each section below is self-contained enough to spawn an
independent PR or task ticket.

---

## Move 1 — Promote path-keyed summaries from "planned" to "shipping"

### Status
`draft` in
[path-keyed-sidecars-for-rag-v0.7.0.md](./path-keyed-sidecars-for-rag-v0.7.0.md);
ready to execute.

### Action

1. Flip the 0.7.0 spec's frontmatter `status: draft` →
   `status: approved, in-progress`.
2. Kick off Task 1 (schema-draft) and Task 2
   (bootstrap-generator) in parallel. These don't depend
   on each other and produce the inputs for Task 3a.
3. Task 3a (polish pipeline) — implement per the prompt
   already drafted in the 0.7.0 spec. Reuse
   attune-author's `polish_template()` provider wiring
   where possible.
4. Task 3b (enrich-all-features) runs the polish across
   all 26 features. Budget ~15 min LLM time + ~1h human
   spot-check.
5. Task 4 (pytest-sidecars) gates release on schema and
   coverage.
6. Task 5 (changelog-release) — 0.6.0 → 0.7.0 bump, tag,
   publish.

### Decision criteria

- Ship 0.7.0 as a minor bump because sidecars are
  additive. No breaking changes for existing consumers.
- After 0.7.0 lands, trigger Move 3 (golden benchmark
  rerun) immediately. Do not wait.

### Target timeline

One focused session: 2-4 hours + ~15 min LLM polish +
~1h review. Could ship within a week if prioritized.

---

## Move 2 — Add Shape 2 fixtures as Task 6 of 0.7.0

### Status
Covered in the 0.7.0 spec body but not yet as a numbered
task. Action: a follow-up PR to the attune-help 0.7.0
spec adds Task 6.

### Why it matters

Fixtures have three jobs that justify their own slot:

1. **Polish pipeline input.** Each feature's fixture
   supplies `target_keywords` to the LLM polish prompt.
   Without fixtures, the LLM guesses at what queries
   users will write; with fixtures, it encodes the exact
   query language into the summary.
2. **Per-feature regression benchmark.** The fixture
   becomes the test that protects a feature's retrieval
   quality from summary drift during future edits.
3. **Contrastive training data.** If fastembed ships
   later, fixtures become query→target pairs for
   embedding fine-tuning or cross-encoder rerank.

### Schema

```
src/attune_help/templates/fixtures/{feature}.yaml
```

Each file:

```yaml
version: 1
feature: {feature-name}
expected_in_top_3:
  - concepts/tool-{feature}.md
  - quickstarts/{skill|run}-{feature}.md
  - references/tool-{feature}.md
queries:
  - "...25 natural-language queries covering:
       - literal keyword queries (easy)
       - pattern-specific queries (medium)
       - intent-shape queries (medium-hard)
       - natural-language phrasing (hard)
       - industry terminology (hard) — CVE, OWASP,
         pen test, backdoor, etc. for security, or
         their domain equivalents for other features
       - edge cases at feature boundaries"
```

### Generation pipeline

Similar to the polish pipeline in Move 1:

1. LLM prompt per feature: "Generate 25 natural-language
   queries a developer would ask when looking for
   {feature}. Cover literal-keyword, pattern-specific,
   intent-shape, natural-phrasing, industry-terminology,
   and feature-boundary cases."
2. Human spot-check for each feature.
3. Run through the current retriever as a sanity check
   before using as polish-pipeline input.

### Integration with Move 1

Generate fixtures **before** running the polish pipeline.
The polish step then consumes fixtures to target
keywords:

```
Task order:
  1 (schema) + 2 (bootstrap) + 6a (fixtures) in parallel
  → 3a (polish pipeline, depends on all three)
  → 3b (enrich all features, depends on 3a)
  → 4 (tests)
  → 5 (release)
```

### Benchmark harness

Update `scripts/benchmark_fixtures.py` (new) to iterate
per-feature and report aggregate P@1 + per-feature
scores. Fail the 0.7.0 release if any feature's P@1
falls below 60% — a weaker-than-hand-crafted but still
meaningful quality gate for the LLM polish output.

### New insight from security-audit validation

Industry terminology (CVE, OWASP, pen test, backdoor)
must be explicit in fixture queries, and the polish
prompt needs a "include domain terminology commonly
used in the industry, even if it doesn't appear in the
template body, as long as it's a genuine synonym for
what the template describes" clause. Without this, the
LLM under-generates synonyms and misses these queries.

---

## Move 3 — Rerun attune-rag golden benchmark after 0.7.0 publishes

### Status
Single-session operational task. No new spec needed; this
documents the procedure.

### Action

Once attune-help 0.7.0 is live on PyPI:

```bash
cd /path/to/attune-rag
git checkout main && git pull
# Bump attune-help floor in pyproject.toml:
#   attune-help>=0.5.1 → attune-help>=0.7.0
uv lock
uv sync --extra dev --extra attune-help
uv run python -m attune_rag.benchmark --verbose
```

Capture the output. Commit the new baseline to
[attune-ai/docs/rag/embeddings-decision-2026-04-17.md](https://github.com/Smart-AI-Memory/attune-ai/blob/main/docs/rag/embeddings-decision-2026-04-17.md)
with a new "Phase 2.5c result" section.

### Expected result

Predicted (based on two single-feature prototypes):
- Precision@1: **78-85%** (up from 66.67% in 0.1.1)
- Recall@3: **82-88%** (up from 73.33%)

### Decision triggered

| Benchmark result | Consequence |
|---|---|
| P@1 ≥ 70% | Move 4 triggers: fastembed stays deferred. Update the decision doc from "Phase 2.5b triggered" to "Phase 2.5b optional, not shipping by default." Ship attune-rag 0.1.2 as the new baseline. |
| P@1 < 70% | Phase 2.5b (fastembed) stays on track as the next milestone. Attune-rag 0.1.2 ships as a summary-enabled release regardless. |

Either way, 0.7.0 + 0.1.2 produces a measurable
retrieval quality improvement.

### Who owns

Single attune-rag PR; ~1 day of focused work.

---

## Move 4 — Reconsider fastembed v0.2.0 priority

### Status
Pre-committed in
[attune-ai/docs/rag/embeddings-decision-2026-04-17.md](https://github.com/Smart-AI-Memory/attune-ai/blob/main/docs/rag/embeddings-decision-2026-04-17.md)
as "Phase 2.5b: triggered". The new evidence shifts this.

### The case for deferring fastembed indefinitely

- The two prototype features both cleared the 70% P@1
  gate via summaries alone (72%, 76%). If the full
  benchmark follows suit, the gate is met without
  fastembed.
- fastembed carries a 35MB install tax that every user
  pays, including those on corpora where keyword
  retrieval already works (after 0.7.0 summaries).
- "Don't ship unused code" was the original motivation
  for the <50MB gate. An empirically-unnecessary
  35MB extension fails that principle.
- The lessons-learned entry ships on prompt caching is
  the local precedent: ship the cheaper lever, defer
  the heavy one until data demands it.

### The case for shipping fastembed anyway

- Users with non-attune-help corpora (their own
  template libraries, Markdown collections, etc.) may
  not have summary metadata. Embeddings give them
  retrieval that doesn't depend on curator attention.
- Embeddings + summaries compound. If the goal is
  90%+ P@1, embeddings help close the last 10-15%.
- Having both retrievers lets users choose by install
  size vs. quality.

### Recommended decision framework

After Move 3 benchmark rerun:

| Scenario | Action |
|---|---|
| Golden P@1 ≥ 80% AND industry fixture P@1 ≥ 70% | Defer fastembed indefinitely. Update decision doc to "Phase 2.5b optional future, not scheduled." Focus energy on the corpus side (Moves 1-3, then per-feature fixtures as standard authoring). |
| Golden P@1 70-80% | Ship fastembed as an optional extra (`attune-rag[embeddings]`), keep keyword retrieval as default. Let users opt in if they hit quality issues on their own corpora. |
| Golden P@1 < 70% | Phase 2.5b stays on track. Fastembed becomes the default retriever for attune-rag 0.2.0, keyword retrieval remains as a fallback for the zero-dep install. |

Writing this matrix **before** the Move 3 rerun, so the
decision criterion can't be reverse-engineered from a
number we like.

### Who owns

Update owner: whoever runs Move 3. The decision doc
update is a ~30 min task once the number is in.

---

## Move 5 — Capture the "summary channel was dead weight" lesson in CLAUDE.md

### Status
Scoped edit to `attune-ai/.claude/CLAUDE.md` Lessons
Learned section.

### Why

Diagnosing this took longer than it should have. The
existing session found attune-rag's SUMMARY_WEIGHT=1.5
was applied to zero real data because sidecar schemas
didn't match loader expectations. The lesson generalizes:
any RAG integration has a "is the metadata actually
reaching the retriever" question that's cheap to verify
and rarely verified.

### Proposed lesson entry

```markdown
- **Metadata can reach a retriever with zero signal if
  the sidecar schema doesn't match the loader's
  expected shape**: attune-rag's `DirectoryCorpus`
  expected path-keyed `summaries.json`, but attune-help
  0.5.1 shipped a feature-keyed one. Result: every one
  of 633 corpus entries had `summary=None` at retrieval
  time, making the 1.5x SUMMARY_WEIGHT apply to zero
  data for months. Always validate that metadata
  actually reaches the retriever before spending time
  tuning retrieval coefficients — a one-line check on
  `sum(1 for e in corpus.entries() if e.summary)` would
  have caught this in minutes instead of weeks.
  Validated by a prototype that replaced the sidecar
  schema on one feature and saw P@1 jump +40 pts.
```

### Action

Single commit to attune-ai `.claude/CLAUDE.md` following
the existing lesson pattern. Can go in the next PR that
touches attune-ai for any reason, or as a standalone
docs PR.

### Who owns

Any session touching attune-ai lessons going forward.
5-min edit.

---

## Sequencing summary

```
Move 1 (0.7.0 spec execution) ────┐
                                  │
Move 2 (Shape 2 fixtures, Task 6) ┤
                                  ├─→ attune-help 0.7.0 ships
                                  │
                                  ↓
                              Move 3 (attune-rag benchmark rerun)
                                  │
                                  ↓
                              Move 4 (fastembed decision)
                                  │
                                  ↓ (independent, can run anytime)
                              Move 5 (CLAUDE.md lesson)
```

Moves 1 + 2 are the only real work; 3-5 are
downstream consequences (benchmark run, decision-doc
edit, lessons edit).

## Success criteria for the roadmap as a whole

1. attune-rag golden benchmark P@1 ≥ 70% (the original
   pre-committed gate).
2. Every feature has a fixture file and polished
   summaries; CI enforces coverage.
3. Decision doc reflects whichever fastembed path the
   Move 3 data supported, with criteria stated
   up-front (Move 4's matrix).
4. CLAUDE.md carries the lesson so the next person
   building a RAG integration doesn't replay the
   feature-keyed-sidecar mistake.

## Risks and open questions

- **Mutual competition once all features are polished.**
  The single-feature prototypes saw some lift from
  everyone-else having null summaries. Net lift across
  26 polished features may compress 10-20%. Move 3
  surfaces the real number.
- **LLM polish quality variance.** Task 4's validation
  (fixture-based regression check per feature) mitigates
  this, but expect 1-2 features to need re-polish or
  manual edit.
- **Industry terminology gaps.** security-audit
  validation surfaced "CVE", "OWASP", "pen test",
  "backdoor" misses. Polish prompt needs an industry-
  terminology clause. Similar gaps may exist for other
  domains (deployment terms for release-prep, ML terms
  if any ML features exist, etc.).
- **Fixtures could become maintenance burden.** 25
  queries × 26 features = 650 queries. Any API rename
  or feature removal requires fixture sync. Mitigation:
  CI check that every fixture's `expected_in_top_3`
  paths resolve to real files.
