# Changelog

All notable changes to `attune-help` are documented here.

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
