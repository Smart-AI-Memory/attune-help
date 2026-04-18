---
name: Path-keyed sidecars for RAG — summaries + cross-links
status: draft
created: 2026-04-18
target-release: 0.7.0
owner: Patrick Roebuck
---

# Path-keyed sidecars for RAG — summaries + cross-links

## Context

`attune-rag` 0.1.x consumes the attune-help template corpus
via `DirectoryCorpus`. The loader reads two sidecars:
`summaries.json` and `cross_links.json`. When each template
file is ingested, the loader does:

```python
summaries.get(path, None)     # expect {path -> str}
cross_links.get(path, ())     # expect {path -> [paths]}
```

Both lookups silently return `None` / `()` against today's
attune-help schemas because:

- `summaries.json` is keyed by **feature name**
  (`"security-audit"`, `"bug-predict"`) — not template path.
  26 entries total.
- `cross_links.json` is a nested
  `{version, stats, links, tag_index, workflow_map}` where
  `links` is keyed by **short node IDs** like
  `"com-auth-strategies"` — not template paths.

Result: every retrieval entry in the 400+ template library
enters the RAG pipeline with `summary=None` and
`related=()`. The `KeywordRetriever.SUMMARY_WEIGHT=1.5`
signal and the related-entries-contribute-score path are
both dead weight on this corpus.

## Problem

Attune-rag 0.1.1 benchmark (15 golden queries) reported
66.67% Precision@1 against this corpus. Four remaining
hard misses are cases where the target concept file lacks
the query tokens in path or content body, so the summary
was the only signal that could have disambiguated. Because
the summary lookup silently fails, those queries are stuck
until either:

- The summary metadata reaches attune-rag in a form it
  understands (this spec), or
- attune-rag switches to embeddings (v0.2.0 fastembed —
  separate track, larger install).

Even for embedding retrieval, richer per-path summaries
will materially improve document vectors.

## Goals

1. Ship a new path-keyed `summaries.json` that maps every
   template file path → a short, keyword-inclusive summary.
2. Ship a new path-keyed `cross_links.json` that maps every
   template path → related template paths.
3. Preserve the existing feature-keyed sidecars for
   backwards compatibility with any current consumer.
4. Enrich summaries to include the specific concepts a
   user is likely to query: `concepts/tool-bug-predict.md`
   should mention "dangerous eval calls, null references,
   race conditions, memory leaks" — not just "predicts
   bugs".

## Non-goals

- Embeddings, retrievers, or any runtime change in
  attune-help itself.
- Changing the HelpEngine API or consumer-facing docs.
- Content rewrite of template bodies (summaries only).
- mkdocs integration (separate discussion).

## End state

```
src/attune_help/templates/
├── summaries.json              # existing, feature-keyed (kept)
├── summaries_by_path.json      # new, path-keyed (primary for RAG)
├── cross_links.json            # existing, nested (kept)
├── cross_links_by_path.json    # new, path-keyed
└── (templates unchanged)
```

attune-rag's `DirectoryCorpus` is updated (separate PR,
attune-rag 0.1.2) to prefer `*_by_path.json` when present
and fall back to the legacy sidecars. Zero breaking
changes in either repo.

Benchmark target after adoption:
- Precision@1 71-75% (crossing the 70% gate)
- Recall@3 80%+
- No regression on easy/medium queries

## Tasks

<task id="1" name="schema-draft">
  <objective>
    Document the new sidecar schemas and publish them as
    JSON Schema files under
    `src/attune_help/templates/schemas/`.
  </objective>
  <files-to-create>
    <file path="src/attune_help/templates/schemas/summaries_by_path.schema.json">
      JSON Schema: object mapping path strings (matching
      `^[a-z]+/.+\.md$`) to summary strings (<= 280 chars).
    </file>
    <file path="src/attune_help/templates/schemas/cross_links_by_path.schema.json">
      JSON Schema: object mapping path strings to arrays
      of path strings (unique, sorted). Max 8 related per
      entry.
    </file>
  </files-to-create>
</task>

<task id="2" name="bootstrap-generator">
  <objective>
    Write a script that generates initial versions of both
    new sidecars by extracting first-heading + first-
    paragraph from each template as a starting summary,
    and by harvesting existing cross-link edges.
  </objective>
  <files-to-create>
    <file path="scripts/generate_path_sidecars.py">
      CLI: `python scripts/generate_path_sidecars.py
      [--dry-run]`. Reads all template .md files,
      extracts heading + first paragraph, writes
      `summaries_by_path.json`. Also translates existing
      `cross_links.json.links` short-ID edges into path
      edges via a name-resolver mapping.
    </file>
  </files-to-create>
  <validation>
    <check>Script idempotent: running twice produces byte-identical output</check>
    <check>Every .md file in templates/ has an entry in output (no silent drops)</check>
    <check>Script emits a report of features with summaries <40 chars (likely too thin)</check>
  </validation>
</task>

<task id="3a" name="llm-polish-pipeline">
  <objective>
    Build an LLM polish pipeline that rewrites each
    bootstrap summary into a 280-char, keyword-inclusive,
    tonally consistent version. Reuse attune-author's
    `polish_template()` where possible so the same
    provider wiring and style prompt apply.
  </objective>
  <files-to-create>
    <file path="scripts/polish_path_summaries.py">
      CLI: `python scripts/polish_path_summaries.py
      [--input summaries_by_path.json]
      [--output summaries_by_path.json]
      [--model claude-haiku-4-5] [--dry-run] [--limit N]`.
      For each entry: pass the bootstrap summary + the
      template body + the known target keywords (if any)
      to the LLM with a "rewrite as ≤280-char summary,
      include domain keywords users would search with,
      declarative sentence, no imperative, no filler"
      prompt. Writes back in place.
    </file>
  </files-to-modify>
  <validation>
    <check>Runs idempotently given the same input + model</check>
    <check>Emits a cost report (input/output tokens per call + total)</check>
    <check>--dry-run prints the diff without writing</check>
  </validation>
</task>

<task id="3b" name="enrich-all-features">
  <objective>
    Apply the polish pipeline to every path in the
    bootstrap sidecar — all 26 features × ~5 templates
    (~130 entries). Comprehensive, not priority-based.
  </objective>
  <reasoning>
    Decision (2026-04-18): polish all 26, not just the
    high-query-volume subset. Rationale: LLM polish drops
    the marginal cost per feature to ~15 sec of API time,
    so the usual "enrich the top N" trade-off doesn't
    apply. Partial enrichment would create two-tier
    summary quality that future maintainers have to reason
    about, and would force a 0.7.1 follow-up to finish.
    For the features where we don't have query-miss data,
    LLM-derived keywords are empirically better than human
    guesses about what users will search for.
  </reasoning>
  <files-to-modify>
    <file path="src/attune_help/templates/summaries_by_path.json">
      Every entry polished, not just the hard-miss set.
      Known target-keyword hints supplied for:
      - concepts/tool-bug-predict.md (dangerous eval, null
        reference, race conditions, memory leaks,
        subprocess patterns)
      - concepts/tool-security-audit.md (vulnerability
        scan, CVE, path traversal, hardcoded secrets)
      - concepts/tool-planning.md (plan new feature,
        spec, decomposition)
      - references/tool-doc-orchestrator.md (orchestrate
        documentation workflow, docs pipeline)
      For all other paths the polish prompt derives
      keywords from the template body.
    </file>
  </files-to-modify>
  <validation>
    <check>Each polished summary under 280 chars</check>
    <check>Each polished summary is grammatical prose</check>
    <check>Cost report documented in CHANGELOG (approx
      $1-4 total at Haiku pricing)</check>
    <check>Spot-check sample of 10 polished entries for
      tone consistency</check>
  </validation>
</task>

<task id="4" name="pytest-sidecars">
  <objective>
    Add a unit test suite that validates both sidecars
    against the JSON Schemas and asserts coverage (every
    template has a summary entry).
  </objective>
  <files-to-create>
    <file path="tests/test_sidecars.py">
      - test_summaries_by_path_matches_schema
      - test_cross_links_by_path_matches_schema
      - test_every_template_has_summary
      - test_every_summary_references_real_path
      - test_no_summary_exceeds_280_chars
      - test_no_entry_has_more_than_8_cross_links
    </file>
  </files-to-create>
</task>

<task id="4b" name="intent-templates">
  <objective>
    Add a "when-to-use" / intent template per feature
    under `tasks/` that describes the feature by the
    questions it answers, not by what it does. Serves
    both humans (discoverable "do I need this?" doc)
    and retrievers (natural-language query surface).
  </objective>
  <files-to-create>
    <file path="src/attune_help/templates/tasks/when-to-use-{feature}.md">
      One file per feature (26 total). Each body opens
      with "Use {feature} when you want to …" and
      enumerates 5-8 concrete scenarios phrased like
      user queries. Example for bug-predict:

        # When to use bug-predict

        Use bug-predict when you want to:

        - Scan for dangerous eval or exec calls before
          they reach production
        - Catch null reference risks in modified files
          prior to merge
        - Find race conditions in concurrent code
        - Surface memory leaks in long-running services
        - Audit subprocess calls for injection risk

        Also useful for: nightly CI bug hunts, preparing
        a release audit, post-incident pattern search.
    </file>
  </files-to-create>
  <validation>
    <check>One file per feature, no gaps</check>
    <check>Each opens with declarative "Use X when you
      want to …"</check>
    <check>Each contains at least 5 scenario queries</check>
  </validation>
</task>

<task id="5" name="changelog-release">
  <objective>
    Add CHANGELOG entry and bump to 0.7.0. Ship via the
    existing publish workflow.
  </objective>
  <files-to-modify>
    <file path="pyproject.toml">
      version 0.6.0 → 0.7.0
    </file>
    <file path="CHANGELOG.md">
      [0.7.0] section noting the additive sidecars, their
      purpose (attune-rag retrieval), schema docs, and
      that old sidecars are unchanged.
    </file>
  </files-to-modify>
</task>

## Coordination with attune-rag

Once attune-help 0.7.0 ships, open attune-rag PR to update
`DirectoryCorpus._build_*_map()` helpers to check for
`summaries_by_path.json` and `cross_links_by_path.json`
first, falling back to the legacy files. Re-run
`python -m attune_rag.benchmark` on the updated corpus and
publish as attune-rag 0.1.2 with the new baseline.

Gate: if 0.1.2 benchmark crosses 70% P@1 using tuned
keyword retrieval + enriched summaries, v0.2.0 fastembed
stays deferred (ship as optional extra only). If still
below gate, fastembed remains the next milestone.

## Sequencing

Two tracks, with one dependency edge between them.

### Track A — attune-help 0.7.0 (this spec)

Sequential within the track:

1. **Task 1 (schema-draft)** and **Task 2 (bootstrap-
   generator)** can run in parallel; neither blocks the
   other and both land as a single PR.
2. **Task 3a (polish pipeline)** comes next — needs the
   bootstrap output as input, and needs the schema to
   validate against. Ship as a second PR so reviewers can
   separate infra from content.
3. **Task 3b (enrich-all-features)** is a pure data run
   of the 3a pipeline. Land in the same PR as 3a if the
   output is clean on the first pass; otherwise split.
4. **Task 4 (pytest-sidecars)** runs last but must block
   release — every path must have a summary, every
   summary must be under 280 chars, schema must match.
5. **Task 5 (changelog-release)** — version bump, push
   signed tag, trigger `publish.yml`, approve the PyPI
   environment gate.

Expected duration: 2-4 hours of focused work + ~15 min of
LLM polish time for 3b.

### Track B — attune-rag 0.1.2 (follow-up, separate repo)

Depends on: attune-help 0.7.0 live on PyPI.

1. Update `DirectoryCorpus._load_sidecar()` to check for
   `*_by_path.json` variants before the legacy files.
2. Bump attune-rag's `[attune-help]` extra dep floor from
   `>=0.5.1` to `>=0.7.0`.
3. Re-run `python -m attune_rag.benchmark` and commit the
   new baseline to
   [docs/rag/embeddings-decision-2026-04-17.md](https://github.com/Smart-AI-Memory/attune-ai/blob/main/docs/rag/embeddings-decision-2026-04-17.md).
4. **Gate decision**: if P@1 >= 70%, v0.2.0 fastembed
   moves from "triggered" to "deferred indefinitely" —
   ship embeddings only as an optional extra for users who
   want cross-corpus use. If P@1 still < 70%, v0.2.0 stays
   the next milestone on track.

Track B is 1-day work once Track A ships.

### No blocking relationship with fastembed v0.2.0

The v0.2.0 embeddings track is independent of this spec —
better summaries improve embedding vectors too, so both
paths compose rather than compete. If Track B clears the
70% gate, v0.2.0 becomes a nice-to-have; if not, v0.2.0
remains on deck with a stronger corpus underneath it
either way.

## Alternatives considered

### Alt 1 — Skip sidecars, go straight to v0.2.0 fastembed

- **Pro**: one track, clear escalation path.
- **Con**: leaves a cheap win on the table. Embeddings
  still benefit from richer per-path summaries — document
  vectors are computed from content the retriever sees,
  and empty summary fields starve that signal. We'd need
  this work eventually regardless of retrieval strategy.
- **Rejected because**: embeddings address the retriever;
  sidecars address the corpus. Different axes, and we
  need both to be good.

### Alt 2 — Embed summaries in template YAML frontmatter

- **Pro**: single source of truth per template file, no
  sync risk between template body and sidecar.
- **Con**: forces attune-rag (and any other consumer) to
  parse YAML frontmatter on ingest; increases per-file
  I/O. Also couples data layout to Markdown — JSON
  sidecars stay provider-agnostic for non-Markdown
  corpora (task library, playbook library, etc.).
- **Rejected because**: the `CorpusProtocol` contract in
  attune-rag is designed around path-keyed metadata, not
  per-entry frontmatter parsing. Preserving that contract
  matters more than avoiding a second file.

### Alt 3 — Hand-write all 26 features without LLM polish

- **Pro**: guaranteed voice and precision.
- **Con**: 3-4 hours of author time; inconsistent tone
  across sessions; no repeatable pipeline for future
  features. Every new concept template added to
  attune-help re-invokes the same cost.
- **Rejected because**: LLM polish + human spot-check
  converges on the same quality for ~5% of the time, and
  the pipeline auto-handles future additions.

### Alt 4 — Keep feature-keyed sidecar as the only source; move adapter logic into attune-rag

- **Pro**: zero change needed in attune-help; all the
  schema mapping logic lives in one consumer.
- **Con**: `DirectoryCorpus` is meant to be generic —
  attune-help-specific mapping code inside it is a leak
  of concerns. Also forces every other attune-rag
  consumer (e.g. future plugin-authored corpora) to know
  about attune-help's short-ID schema.
- **Rejected because**: the corpus is where the schema
  should live. `attune-rag.corpus.attune_help` is the
  right home if any attune-help-specific adapter is
  needed; but the cleaner answer is to ship schemas the
  generic loader can consume — which is this spec.

### Alt 5 — Build a smarter retriever (stemming, query expansion) instead of richer summaries

- **Pro**: no corpus changes.
- **Con**: we proved in attune-rag 0.1.1 that retriever
  tuning alone caps at ~66.67% P@1 on this corpus. The
  remaining misses are corpus-content problems, not
  algorithm problems. Query expansion helps marginally
  but hits diminishing returns without richer signal in
  the corpus itself.
- **Rejected because**: the benchmark plateau is data,
  not conjecture.

## Polish prompt (Task 3a)

The prompt below is the system message for the summary
polish pipeline. Provider-agnostic — meant for Claude,
GPT-4, or Gemini. Temperature 0.2 recommended (deterministic
enough for idempotency, enough variance to rewrite bad
bootstraps).

````text
You are writing a one-line summary for a developer-
documentation template in the attune-help library. These
summaries feed a keyword-based RAG retriever: developers
ask questions in natural language, and the retriever ranks
templates by how well their summaries overlap with the
query. So the summary needs to be keyword-dense AND
grammatical — for the retriever AND for a human scanning
the help system.

## Constraints

- Length: between 180 and 280 characters. Count the
  characters. Below 180 is thin; above 280 fails the
  schema.
- Voice: declarative, not imperative. "Scans source
  files for …" not "Scan your source files for …".
- Grounding: every domain-specific term you use must
  appear in, or be clearly implied by, the provided
  `template_body`. If a keyword you want to use isn't
  there, find a synonym that IS there or drop it.
- Idempotency: if `bootstrap_summary` already meets the
  constraints above, return it with minimal edits. Do
  not rewrite for variety.

## Category-specific shape

- `concepts/` — WHAT the feature is and which concrete
  patterns or situations it addresses. 3-5 noun-phrase
  keywords feels right.
- `quickstarts/` — the OUTCOME after following the
  steps. Action verbs + target objects.
- `references/` — WHAT is documented (CLI flags, API
  surface, output format, exit codes). Technical terms
  users would look up.
- `tasks/` — the TASK accomplished. The domain of the
  task.
- `errors/` `warnings/` `faqs/` — brief one-liner
  describing the symptom or question. Do NOT pad: these
  categories are penalized in the retriever and long
  summaries actively hurt ranking. 60-150 chars is ideal.

## Keyword hints

If `target_keywords` is provided, the summary MUST
mention each in natural prose (not a comma pile). If
it's empty, derive 3-5 keywords from `template_body`.

## Output format

Return ONLY the summary text. No quotes, no markdown,
no "Summary:" prefix, no trailing whitespace, no
trailing period if the summary is a fragment.

## Examples

---
INPUT:
  path: concepts/tool-bug-predict.md
  category: concepts
  feature_name: bug-predict
  bootstrap_summary: "Bug prediction scans your codebase
    for patterns that historically cause production
    incidents."
  target_keywords: ["dangerous eval", "null reference",
    "race conditions", "memory leaks", "subprocess
    patterns"]

OUTPUT:
Scans source files for the patterns that historically
cause production bugs — dangerous eval calls, null
references, race conditions, memory leaks, and unsafe
subprocess use. Reports predicted risks before they
surface at runtime.

---
INPUT:
  path: quickstarts/run-security-audit.md
  category: quickstarts
  feature_name: security-audit
  bootstrap_summary: "Run attune workflow run
    security-audit to scan your codebase."
  target_keywords: []

OUTPUT:
Scan a codebase for security vulnerabilities —
hardcoded secrets, eval/exec, path traversal,
injection risks — with a single `attune workflow run
security-audit` command. Returns findings grouped by
severity.

---
INPUT:
  path: references/tool-doc-orchestrator.md
  category: references
  feature_name: doc-orchestrator
  bootstrap_summary: "doc-orchestrator chains
    documentation workflows across a repo."
  target_keywords: ["orchestrate documentation workflow",
    "docs pipeline"]

OUTPUT:
Reference for doc-orchestrator — CLI flags, stage
configuration, and output contract for orchestrating a
documentation workflow across a repository. Covers
pipeline composition, stage skip rules, and exit
codes.

---
INPUT:
  path: errors/bug-predict-dangerous-eval-flags-subprocess-exec.md
  category: errors
  feature_name: bug-predict
  bootstrap_summary: "When bug-predict flags
    subprocess.exec calls as dangerous_eval, it's a
    false positive."
  target_keywords: []

OUTPUT:
bug-predict flags `subprocess.exec()` as dangerous_eval
via regex substring match. False positive — the exec is
intentional and safe.

---

Now summarize this template:

  path: {path}
  category: {category}
  feature_name: {feature_name}
  bootstrap_summary: {bootstrap_summary}
  target_keywords: {target_keywords}
  template_body: {first_2000_chars}
````

## Polish pipeline checks

After calling the LLM, the pipeline MUST enforce:

1. **Length bounds** — 180 ≤ len(summary) ≤ 280 for
   primary categories, 60 ≤ len(summary) ≤ 150 for
   `errors/warnings/faqs`.
2. **No quoting artifacts** — strip leading/trailing
   quotes, remove "Summary:" prefixes.
3. **Grounding** — tokenize the summary, tokenize the
   template body, assert every noun/verb token in the
   summary appears in the body OR was in
   `target_keywords`. Stopwords excluded. If a token
   fails, flag for human review (don't auto-reject —
   model might be using a legitimate synonym the
   tokenizer can't recognize).
4. **Imperative detection** — reject summaries starting
   with bare verbs ("Run", "Install", "Configure") by
   default; retry with the prompt reinforced.
5. **Duplicate-keyword cap** — no keyword appears more
   than twice in the summary.

On validation failure, retry up to 2 times with the
failing check added to the prompt as a negative
constraint ("previous attempt failed check X; avoid
Y"). If still failing after 3 attempts, emit the last
attempt with a warning and move on — manual review
queue.

## Risks

- **Summary rewrites drift from feature intent.** Mitigation:
  keep feature-keyed `summaries.json` unchanged as the
  "canonical" short summary; use path-keyed variant for
  keyword-dense retrieval hints.
- **Bootstrap script overgenerates noise.** Mitigation:
  coverage test + manual spot-check for the top 26 features.
- **Maintenance burden doubles.** Mitigation: CI check that
  feature-keyed and path-keyed summaries don't contradict
  each other for the same feature.
- **LLM polish introduces hallucinated keywords.**
  Mitigation: polish prompt instructs "only use keywords
  that appear in or are clearly implied by the template
  body"; spot-check 10 samples; add a regression test
  that flags summaries whose keywords don't appear
  anywhere in the corresponding template.
