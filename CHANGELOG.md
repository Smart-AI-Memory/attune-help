# Changelog

All notable changes to `attune-help` are documented here.

## 0.9.0 — 2026-04-24

Supersedes the unreleased 0.8.0 draft. Combines the manifest +
staleness extraction from that draft with multi-doc support and
a top-level narrative-docs bucket.

### Added

- **`manifest.py`** — Feature manifest parser with project-doc field
  support. Extends the `Feature` dataclass with `doc_kinds`,
  `doc_paths` (list), `arch_path`, and `doc_nav_section` fields so
  `features.yaml` can register generated `docs/` output paths
  alongside existing `.help/` template mappings. Exports
  `load_manifest`, `save_manifest`, `match_files_to_features`,
  `resolve_topic`, `is_safe_feature_name`, and `slugify`.

- **`Feature.doc_paths: list[str]`** — A feature may now register
  multiple docs. Single-file features (e.g. `cli` →
  `cli-reference.md`) set one entry; multi-file features (e.g.
  `memory` with four how-to guides) set the full list.
  `Feature.__post_init__` coalesces between `doc_path` (scalar,
  deprecated) and `doc_paths` (list) so callers can read either
  attribute without a None mismatch. Loader accepts both forms;
  writer always emits `doc_paths`.

- **Top-level `_docs:` bucket** — Hand-written narrative docs that
  don't belong to any single feature (FAQ, glossary, installation,
  etc.) can be registered in the manifest via a `_docs:` list at
  the top level. Exposed as `FeatureManifest.docs: list[str]`.
  Tracked for discovery and mkdocs nav; never regenerated from
  source.

- **`staleness.py`** — Dual-format staleness detection covering both
  `.help/` templates and project `docs/` files in one
  `check_staleness()` call. Iterates `doc_paths` so a feature with
  multiple registered docs produces one `DocStaleness` entry per
  path.

  - Help templates: reads `source_hash` from YAML frontmatter in
    `concept.md` (unchanged behaviour).
  - Project docs: reads `source_hash` from an HTML comment footer
    appended by `attune-author`'s doc generator:
    `<!-- attune-generated: source_hash=... feature=... kind=... generated_at=... -->`.
    Reports a doc as stale when the hash mismatches or the file is
    absent entirely.

  New data classes: `DocStaleness`, updated `StalenessReport` with
  `help_entries` / `doc_entries` split and `stale_docs` property.
  New helpers: `parse_doc_footer`, `build_doc_footer`,
  `compute_source_hash`.

- **Public API exports** — all new symbols are exported from
  `attune_help.__init__` so `attune-author` can import them without
  reaching into submodules.

### Migration

- Legacy manifests using `doc_path: <scalar>` continue to load —
  the loader coalesces the scalar into a single-entry `doc_paths`
  list. No YAML changes required for consumers still on the
  scalar form.
- Consumers reading attributes should prefer `feature.doc_paths`
  going forward. `feature.doc_path` remains populated as
  `doc_paths[0]` for backward compatibility.

## 0.7.0 — Unreleased

### Added

- **Path-keyed summary sidecar** for RAG consumers.
  `src/attune_help/templates/summaries_by_path.json`
  maps template paths (`concepts/tool-bug-predict.md`)
  to keyword-rich, declarative summaries. attune-rag's
  `DirectoryCorpus` reads this schema directly — the
  existing feature-keyed `summaries.json` was silently
  ignored by path-keyed consumers.
- **Per-feature query fixtures** under
  `src/attune_help/templates/fixtures/{feature}.yaml`.
  Each fixture lists 25 natural-language queries a
  user would ask for that feature. Three jobs: polish
  pipeline input (`target_keywords`), per-feature
  regression benchmark, and contrastive training data
  if embeddings ship later.
- **Dev-only polish + benchmark scripts** under
  `scripts/`:
  - `generate_fixtures.py` — LLM-generates the 25-query
    fixture per feature via Claude Haiku 4.5.
  - `polish_summaries.py` — LLM-polishes each template
    into a length-bounded, keyword-rich,
    differentiation-aware summary.
  - `benchmark_all_fixtures.py` — runs every feature's
    fixtures through attune-rag and reports per-feature
    + overall Precision@1 / Recall@3.
  - `differentiation_hints.yaml` — per-feature USP
    statements that prevent cross-routing between
    overlapping features.
- **User-facing CLI** — `attune-help` console script
  exposes `lookup`, `list`, `search`, and `simpler`
  subcommands over the same `HelpEngine` API the MCP
  server uses. `python -m attune_help` also works.

### Retrieval quality (26 features × 25 queries = 650)

| Metric | Before (0.5.1) | After (0.7.0) |
|---|---|---|
| Precision@1 | ~0% effective (summaries ignored) | **71.7%** |
| Recall@3 | ~0% effective | **81.5%** |

Clears the 70% P@1 gate pre-committed in
[attune-ai/docs/rag/embeddings-decision-2026-04-17.md](https://github.com/Smart-AI-Memory/attune-ai/blob/main/docs/rag/embeddings-decision-2026-04-17.md).
Moves the fastembed v0.2.0 embeddings track from
"committed next milestone" to "deferred / optional".

Known quality variance: 6 features below the 60% P@1
gate (spec, code-quality, planning, refactor-plan,
workflow-orchestration, security-audit) demonstrate
the mutual-competition effect — once every feature has
polished summaries, overlapping features steal each
other's queries. Scheduled for 0.7.1 follow-up with
targeted differentiation tuning.

### Changed

- **Development Status promoted to Beta** (was Alpha).
  attune-help is now a core dependency of attune-ai
  (Production/Stable).
- **PyPI project URLs** point to the extracted repo
  (`Smart-AI-Memory/attune-help`). Added `Changelog`
  and `Issues` URLs.

### Consumer impact

- attune-ai and attune-author both currently pin
  `attune-help>=0.5.1,<0.6`. Those caps need to bump to
  `<0.8` and attune-rag's `DirectoryCorpus` should be
  pointed at `summaries_by_path.json` (new schema) so
  the +72% P@1 lift actually reaches users. Tracked as
  attune-rag 0.1.2.
- The originally-planned 0.6.0 release (CLI + Beta
  classifier only) was never published; its scope is
  rolled forward into this 0.7.0 release.

## 0.5.1 — 2026-04-12

### Fixed

- **[BLOCKING]** `lookup_simpler` MCP handler created a
  fresh `LocalFileStorage()` to read depth back instead
  of using the engine's own storage instance — broke
  custom storage backends.
- `list_topics` parameter renamed from `type` to
  `type_filter` to avoid shadowing the Python builtin.
- `precursor_warnings` extension and filename maps
  extracted to module-level constants (`_EXT_TAGS`,
  `_NAME_TAGS`), reducing the method from 110 to ~10
  lines.
- Handlers category-name map consolidated: now imports
  `_PREFIX_MAP` from `templates.py` instead of
  re-declaring it.
- Repeated string-validation boilerplate across all 10
  MCP handlers extracted into a shared `_require_str()`
  helper (~30 lines removed).
- `_auto_detect_renderer` return typed as
  `Callable[[PopulatedTemplate], str]` instead of `Any`.
- Added `from __future__ import annotations` to
  `demos/__init__.py`.

### Tests

- 20 new tests: renderer branches (error/warning/tip,
  marketplace, CLI plain), `engine.get()` coverage, and
  MCP handler error-path coverage.
- Overall coverage: 78% → 84%.

## 0.5.0 — 2026-04-11

MCP layer catches up to the 0.4 `HelpEngine` public API.
Everything added to the Python API in 0.4 is now
reachable from an MCP client.

### Added

- **`lookup_simpler`** MCP tool — step a topic one depth
  level back down, mirroring `HelpEngine.simpler()`.
- **`lookup_list_topics`** MCP tool — flat slug
  enumeration optionally filtered by type
  (`concepts`, `tasks`, `references`, …).
- **`lookup_search`** MCP tool — fuzzy slug search
  returning ranked `{slug, score}` hits.
- **`lookup_suggest`** MCP tool — "did you mean" slug
  suggestions.
- `lookup_reset` now accepts an optional `topic`
  parameter to clear a single topic instead of the full
  session, mirroring `HelpEngine.reset(topic)`.
- `lookup_status` now returns the full per-topic depth
  map (`topics`) and LRU order (`order`) alongside the
  legacy `last_topic` / `depth_level` fields.
- `"json"` is now an accepted renderer across every MCP
  tool that renders content — previously only reachable
  from the Python API.
- Public `attune_help.engine.VALID_RENDERERS` constant so
  downstream code can derive allowlists from the same
  source the engine uses.

### Fixed

- Renderer allowlist drift between `HelpEngine` and the
  MCP layer. The handler `_VALID_RENDERERS` frozenset
  and the `tool_schemas` JSON enum now both derive from
  `engine.VALID_RENDERERS`, so adding a renderer to the
  engine automatically propagates to MCP.
- MCP `lookup_reset` previously wrote the legacy
  (pre-0.4) session schema, bypassing the per-topic
  history introduced in 0.4. It now delegates to
  `HelpEngine.reset()`, which writes the current schema.
- MCP tool count assertion was hardcoded. It now uses
  the dispatch table as the source of truth so adding
  tools no longer forces mechanical test updates.

### Changed

- Nothing breaking. All existing MCP tool names and
  response shapes are preserved. New fields on
  `lookup_status` are additive; the `topic` parameter on
  `lookup_reset` is optional.

## 0.4.0 — 2026-04-11

### Added

- `HelpEngine.list_topics(type=None, limit=None)` —
  enumerate available topic slugs.
- `HelpEngine.search(query, limit=10)` — fuzzy slug
  search returning `(slug, score)` tuples.
- `HelpEngine.suggest(topic, limit=5)` — ranked
  suggestions for misspelled topics.
- `HelpEngine.lookup(..., suggest_on_miss=True)` — opt-in
  "did you mean" string when a lookup fails.
- `HelpEngine.simpler(topic)` — step one depth level
  back down without resetting session state.
- `HelpEngine.reset(topic=None)` — clear depth for one
  topic or the whole session.
- `HelpEngine.set_renderer(name)` — swap renderer at
  runtime.
- `renderer="json"` — deterministic structured output for
  apps, web dashboards, and snapshot tests.
- New `attune_help.discovery` module (topic index,
  search, suggest).
- `precursor_warnings` now recognizes JavaScript,
  TypeScript, JSX/TSX, Rust, Go, Ruby, and Java files.

### Fixed

- `HelpEngine.preamble()` now resolves real bundled
  templates. Previously it only looked at the nested
  `<feature>/task.md` demo layout and silently returned
  `None` for the flat `tasks/use-<feature>.md` tree.
- Progressive depth no longer resets when users
  interleave topics. Per-topic depth history replaces
  the single-slot `last_topic`, bounded by an LRU cap
  of 32 topics.
- Depth-2 lookups now emit a terminal prompt
  (`"reference — deepest level; say 'simpler' to step
  back"`) instead of nothing.
- `render_claude_code` no longer drops the body for
  `concept`, `task`, or unknown template types.
- `HelpEngine.get_summary()` falls back to the bundled
  `summaries.json` when an override directory doesn't
  ship one.
- `auto` renderer now respects `sys.stdout.isatty()` —
  piped output gets plain text, terminal output gets
  rich.

### Changed

- Unknown renderer names now raise `ValueError` in
  `HelpEngine.__init__` and `set_renderer()`. Previously
  they logged a warning and silently fell back to
  `plain`.
- Session schema gains `topics` and `order` fields for
  per-topic depth tracking. Legacy session files are
  read-migrated transparently — no action required for
  existing users.

## 0.3.1

Previous release. See git history for details.
