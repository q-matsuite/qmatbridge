"""Live OPTIMADE checks (no key needed).  Run with ``pytest -m integration``."""

from __future__ import annotations

import pytest

from qmatbridge.adapters.optimade import (
    OptimadeAdapterConfig,
    fetch_entry_from_optimade,
)

pytestmark = pytest.mark.integration


def test_materials_project_silicon() -> None:
    cfg = OptimadeAdapterConfig(encut_ev=520.0, timeout_s=60.0)
    entry = fetch_entry_from_optimade("mp:mp-149", cfg)
    s = entry.reference.structure
    assert s.formula_reduced == "Si" and s.num_sites == 2
    assert entry.hamiltonian.num_electrons == 8
    assert s.lattice.a == pytest.approx(3.85, abs=0.1)


def test_alexandria_entry() -> None:
    cfg = OptimadeAdapterConfig(
        encut_ev=520.0,
        timeout_s=60.0,
        valence_charges={"Cs": 9.0, "B": 3.0, "C": 4.0},
    )
    entry = fetch_entry_from_optimade("alexandria-pbe:agm000999956", cfg)
    s = entry.reference.structure
    assert s.formula_reduced == "C3B3Cs" and s.num_sites == 14
    assert entry.hamiltonian.num_electrons == 2 * 9 + 6 * 3 + 6 * 4
