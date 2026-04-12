"""End-to-end test covering discovery → progressive
depth → simpler → renderer switch → suggest-on-miss."""

from __future__ import annotations

import json
from pathlib import Path

from attune_help import HelpEngine, LocalFileStorage


def test_full_enhanced_flow(tmp_path: Path) -> None:
    eng = HelpEngine(storage=LocalFileStorage(storage_dir=tmp_path))

    # 1. Discoverability
    hits = eng.search("security")
    assert hits, "search should find something for 'security'"
    slug_hit = next(
        (s for s, _ in hits if "security" in s),
        None,
    )
    assert slug_hit is not None

    # 2. Progressive depth climb
    first = eng.lookup("security-audit")
    assert first is not None
    second = eng.lookup("security-audit")
    assert second is not None
    third = eng.lookup("security-audit")
    assert third is not None
    assert "simpler" in third, "depth-2 prompt must mention 'simpler'"

    # 3. Step back down
    stepped = eng.simpler("security-audit")
    assert stepped is not None
    session = eng._storage.get_session("default")
    assert session["topics"]["security-audit"] == 1

    # 4. Interleave with a second topic, then return
    eng.lookup("code-quality")
    back = eng.lookup("security-audit")
    assert back is not None
    session = eng._storage.get_session("default")
    assert session["topics"]["security-audit"] == 2
    assert session["topics"]["code-quality"] == 0

    # 5. Runtime renderer switch to JSON
    eng.reset("security-audit")
    eng.set_renderer("json")
    out = eng.lookup("security-audit")
    assert out is not None
    payload_text = out.split("\n\n*(")[0]
    payload = json.loads(payload_text)
    assert "template_id" in payload
    assert "sections" in payload

    # 6. Miss handling with suggest_on_miss
    eng.set_renderer("plain")
    miss = eng.lookup("scurity-audit", suggest_on_miss=True)
    assert miss is not None
    assert "Did you mean" in miss or "No help" in miss


def test_bundled_preamble_works_end_to_end() -> None:
    eng = HelpEngine()
    # Feature slug corresponds to `tasks/use-security-audit.md`.
    preamble = eng.preamble("security-audit")
    assert preamble is not None
    assert len(preamble) > 0
