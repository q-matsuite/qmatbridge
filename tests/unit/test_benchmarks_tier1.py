"""Consistency tests for the Tier-1 benchmark specification."""

from __future__ import annotations

import pytest

from benchmarks.build_tier1_fixtures import check_entry
from benchmarks.tier1 import MP_VALENCE, TIER1
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


def test_spec_keys_and_ids_unique() -> None:
    assert len({s.key for s in TIER1}) == len(TIER1)
    assert len({s.mp_id for s in TIER1}) == len(TIER1)


def test_planned_ids_do_not_collide_with_tier1() -> None:
    from benchmarks.tier1 import PLANNED

    assert not {p[1] for p in PLANNED} & {s.mp_id for s in TIER1}


def test_all_species_have_valence() -> None:
    for spec in TIER1:
        assert set(spec.cell_species) <= set(MP_VALENCE)


@pytest.mark.parametrize(
    ("key", "electrons"),
    [("Si", 8), ("GaN", 36), ("LiCoO2", 24)],
)
def test_expected_electrons(key: str, electrons: int) -> None:
    spec = next(s for s in TIER1 if s.key == key)
    assert spec.expected_electrons == electrons


def _entry(species: list[str], electrons: int, spin: bool) -> QMatEntry:
    lat = LatticeMetadata(a=1, b=1, c=1, alpha=90, beta=90, gamma=90)
    return QMatEntry(
        reference=MaterialReference(
            provenance=SourceProvenance(ExternalIdentifier("materials_project", "x")),
            structure=StructureMetadata("X", "X", len(species), species, lat),
        ),
        hamiltonian=HamiltonianMetadata(
            electrons, spin, BasisMetadata(type="plane_wave")
        ),
    )


def test_check_entry_accepts_match_and_flags_mismatch() -> None:
    si = next(s for s in TIER1 if s.key == "Si")
    assert check_entry(si, _entry(["Si", "Si"], 8, False)) == []
    problems = check_entry(si, _entry(["Si", "Ge"], 10, True))
    assert len(problems) == 3


def test_fixture_script_runs_directly_from_any_directory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Regression: `python benchmarks/build_tier1_fixtures.py` must import."""
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "benchmarks/build_tier1_fixtures.py"
    out = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    assert "--site" in out.stdout
