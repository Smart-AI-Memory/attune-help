# Contributing to attune-help

## Dev setup

```bash
uv sync --extra dev && uv run pre-commit install
```

That installs the dev toolchain and the git pre-commit hooks. From then
on, `black`, `ruff`, `detect-secrets`, and the standard file hygiene
hooks run automatically on every commit.

To run the full suite against the whole tree (what CI enforces):

```bash
uv run pre-commit run --all-files
```

The hooks deliberately **exclude** the generated, LLM-polished content
under `src/attune_help/templates/` and `src/attune_help/demos/` — those
files are byte-exact and must not be rewritten by the hygiene hooks.

The same check runs in CI on every pull request (`.github/workflows/lint.yml`)
and fails the build on any violation, so a clean local run keeps PRs green.

## Tests

```bash
uv run pytest
```
