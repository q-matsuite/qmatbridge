"""Live OQMD check (no key needed).  Run with ``pytest -m integration``."""

from __future__ import annotations

import pytest

from qmatbridge.adapters.oqmd import OQMDAdapterConfig, fetch_entry_from_oqmd

pytestmark = pytest.mark.integration


def test_silicon_entry_is_fetchable() -> None:
    entry = fetch_entry_from_oqmd(1214579, OQMDAdapterConfig(timeout_s=60.0))
    s = entry.reference.structure
    assert s.formula_reduced == "Si" and s.num_sites == 2
    assert entry.hamiltonian.num_electrons == 8
    assert s.lattice.a == pytest.approx(3.86, abs=0.1)
