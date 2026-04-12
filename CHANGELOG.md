# Changelog

All notable changes to `attune-help` are documented here.

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
