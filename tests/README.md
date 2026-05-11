# attune-help tests

## Running locally

```bash
# Full suite (requires the deprecated authoring shims to resolve)
pip install -e ".[dev,authoring]"
pytest

# Zero-dep contract: shim tests skip via pytest.importorskip
pip install -e ".[dev]"
pytest

# With coverage (matches CI's ubuntu x py3.11 cell)
pip install -e ".[dev,authoring]"
pytest --cov --cov-report=term-missing
```

The `slow` marker covers tests that create real venvs
(`test_zero_dep_install.py`). Skip with `pytest -m "not slow"` for fast
iteration.

## LLM mocking standard

attune-help itself makes no LLM calls. Cross-layer integration tests that
*could* exercise an LLM follow the **attune-author reference pattern**:

- Strip `ANTHROPIC_API_KEY` via an autouse fixture so a misconfigured
  test never reaches the network.
- Patch `anthropic.Anthropic` at import time, not at call site.
- Reset module-level singletons (e.g. `_RagPipeline`) between tests with
  an autouse fixture so a leaked patch doesn't poison later tests.

See `attune-author/tests/conftest.py` (`_lenient_polish_by_default`,
`_reset_rag_pipeline`). Pass 2 of the test-strategy spec will formalize
this into a shared `docs/testing-conventions.md` across layers.

## What's tested vs. not

Tracked in
`/Users/patrickroebuck/attune/specs/test-strategy/current-state.md`. After
pass 1, the highest-value remaining gaps in this layer are:

- `cli.py` (~70% branch coverage) — argparse error paths
- `engine.py` (~86%) — depth-progression edge cases
- `transformers.py` (~78%) — channel-specific render branches

Pass 2 will revisit thresholds and target those areas if needed.

## Architectural contracts under test

- **`tests/test_zero_dep_install.py`** — guards
  [tech.md](../../tech.md) ADR-002 (zero required deps beyond
  `python-frontmatter`). Spins up a fresh venv per test case; marked
  `@pytest.mark.slow`.
- **`tests/test_storage_protocol.py`** — reusable mixin verifying the
  `SessionStorage` Protocol contract. New backends (Redis, DB) inherit
  from `StorageProtocolTester` and override `_make_storage()`.
- **`tests/test_authoring_shims.py`** — verifies the deprecated re-export
  shims still resolve correctly while the `[authoring]` extra is
  installed. Sunset 2026-07-07.
