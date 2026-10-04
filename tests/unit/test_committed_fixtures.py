"""The committed Tier-1 fixtures must agree with the Tier-1 spec."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.tier1 import TIER1

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("spec", TIER1, ids=lambda s: s.key)
def test_fixture_matches_spec(spec) -> None:  # type: ignore[no-untyped-def]
    path = ROOT / "benchmarks/fixtures" / spec.fixture_name
    if not path.exists():
        pytest.skip("fixtures not generated yet (see benchmarks/build_tier1_fixtures.py)")
    e = json.loads(path.read_text())
    ref, ham = e["reference"], e["hamiltonian"]
    assert ref["provenance"]["primary"]["identifier"] == spec.mp_id
    assert sorted(ref["structure"]["species"]) == sorted(spec.cell_species)
    assert ham["num_electrons"] == spec.expected_electrons
    assert ham["spin_polarized"] == spec.spin_polarized
    assert ref["provenance"]["functional"] == spec.functional
    assert ham["basis"]["type"] == "plane_wave"
    assert ham["basis"]["num_plane_waves"] > 0


def test_site_data_matches_fixtures() -> None:
    site = ROOT / "website/data/examples.json"
    if not site.exists():
        pytest.skip("site data not generated yet")
    for rec in json.loads(site.read_text()):
        fx = json.loads((ROOT / "benchmarks/fixtures" / f"{rec['key']}.json").read_text())
        assert rec["entry"] == fx
        assert len(rec["sites"]) == fx["reference"]["structure"]["num_sites"]


def test_no_secrets_in_generated_data() -> None:
    import re

    for p in [*(ROOT / "benchmarks/fixtures").glob("*.json"), ROOT / "website/data/examples.json"]:
        if p.exists():
            assert "MP_API_KEY" not in p.read_text(), p
            # 64-hex hashes are expected; a bare 32-char token would be a leaked key
            assert not re.search(r'"[A-Za-z0-9]{32}"', p.read_text()), p
