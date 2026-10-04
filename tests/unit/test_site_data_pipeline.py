"""End-to-end test of the fixture/site-data pipeline with a fake MP client."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from benchmarks import build_tier1_fixtures as b
from benchmarks.tier1 import TIER1, BenchmarkSpec
from qmatbridge.schema import (
    BasisMetadata,
    ExternalIdentifier,
    HamiltonianMetadata,
    LatticeMetadata,
    MaterialReference,
    QMatEntry,
    SourceProvenance,
    StructureMetadata,
)
from tools.build_site import build

ROOT = Path(__file__).resolve().parents[2]
# Fields the page's JavaScript reads from each record (see index.template.html).
PAGE_FIELDS = {
    "key", "label", "category", "description", "mp_id", "formula", "spacegroup",
    "crystal_system", "lattice", "sites", "electrons", "spin_polarized",
    "functional", "ecut_ev", "num_plane_waves", "hash", "retrieved_at", "entry",
}


def _entry_for(spec: BenchmarkSpec) -> QMatEntry:
    lat = LatticeMetadata(
        a=4.0, b=4.0, c=4.0, alpha=90, beta=90, gamma=90,
        spacegroup_number=1, spacegroup_symbol="P1", crystal_system="cubic",
    )
    species = list(spec.cell_species)
    return QMatEntry(
        reference=MaterialReference(
            provenance=SourceProvenance(
                ExternalIdentifier("materials_project", spec.mp_id),
                functional=spec.functional,
                retrieved_at="2026-01-01T00:00:00+00:00",
            ),
            structure=StructureMetadata(
                "X", "X", len(species), species, lat
            ),
        ),
        hamiltonian=HamiltonianMetadata(
            spec.expected_electrons,
            spec.spin_polarized,
            BasisMetadata("plane_wave", cutoff_energy_ev=520.0, num_plane_waves=99),
        ),
    )


@pytest.fixture()
def fake_mp(monkeypatch: pytest.MonkeyPatch) -> None:
    specs = {s.mp_id: s for s in TIER1}

    class Client:
        def __enter__(self) -> Client:
            return self

        def __exit__(self, *a: object) -> None:
            return None

    # main() refuses to start without a key; the fake client never uses it.
    monkeypatch.setenv("MP_API_KEY", "test-key-not-used")
    monkeypatch.setattr(b, "_open_client", lambda key, cfg: Client())
    monkeypatch.setattr(
        b, "fetch_entry_from_mp", lambda mp_id, **kw: _entry_for(specs[mp_id])
    )
    monkeypatch.setattr(
        b,
        "_summary_doc",
        lambda mpr, mp_id, ms: {
            "structure": {
                "sites": [
                    {"species": [{"element": el, "occu": 1}], "abc": [0.0, 0.0, 0.0]}
                    for el in specs[mp_id].cell_species
                ]
            }
        },
    )


def test_pipeline_writes_fixtures_and_page_data(
    fake_mp: None, tmp_path: Path
) -> None:
    site = tmp_path / "examples.json"
    rc = b.main(["--out", str(tmp_path / "fx"), "--site", str(site)])
    assert rc == 0
    assert {p.name for p in (tmp_path / "fx").iterdir()} == {
        s.fixture_name for s in TIER1
    }
    records: list[dict[str, Any]] = json.loads(site.read_text())
    assert [r["key"] for r in records] == [s.key for s in TIER1]
    for r in records:
        assert PAGE_FIELDS <= set(r)
        assert len(r["hash"]) == 64
        assert {"el", "frac"} <= set(r["sites"][0])
        assert set(r["lattice"]) == {"a", "b", "c", "alpha", "beta", "gamma"}

    # and the page builds with them embedded
    out = tmp_path / "index.html"
    assert build(site, ROOT / "website/index.template.html", out) == len(TIER1)
    html = out.read_text()
    assert '"key":"GaN"' in html and "__EXAMPLES_JSON__" not in html


def test_mismatch_writes_nothing(
    fake_mp: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def bad(mp_id: str, **kw: Any) -> QMatEntry:
        e = _entry_for(next(s for s in TIER1 if s.mp_id == mp_id))
        e.hamiltonian.num_electrons += 1
        return e

    monkeypatch.setattr(b, "fetch_entry_from_mp", bad)
    site = tmp_path / "examples.json"
    assert b.main(["--out", str(tmp_path / "fx"), "--site", str(site)]) == 1
    assert not site.exists()
    assert not list((tmp_path / "fx").glob("*.json"))


def test_page_reads_only_fields_the_pipeline_writes() -> None:
    """Every ``ex.<field>`` the page script touches must be in the record."""
    js = (ROOT / "website/index.template.html").read_text()
    used = set(re.findall(r"\bex\.([a-z_]+)", js))
    assert used <= PAGE_FIELDS | {"sites", "lattice"}, used - PAGE_FIELDS
