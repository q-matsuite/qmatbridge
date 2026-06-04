"""Shared pytest fixtures for the QMatBridge test suite."""

from __future__ import annotations

import pytest

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


@pytest.fixture()
def minimal_entry() -> QMatEntry:
    """Return a minimal but fully valid QMatEntry for testing."""
    ref = MaterialReference(
        provenance=SourceProvenance(
            primary=ExternalIdentifier(
                source="test_db",
                identifier="test-001",
            ),
            functional="PBE",
        ),
        structure=StructureMetadata(
            formula_reduced="Si",
            formula_unit_cell="Si2",
            num_sites=2,
            species=["Si", "Si"],
            lattice=LatticeMetadata(
                a=3.867, b=3.867, c=3.867,
                alpha=60.0, beta=60.0, gamma=60.0,
                spacegroup_number=227,
                spacegroup_symbol="Fd-3m",
            ),
        ),
    )
    ham = HamiltonianMetadata(
        num_electrons=8,
        spin_polarized=False,
        basis=BasisMetadata(type="plane_wave", cutoff_energy_ev=520.0),
        num_bands=16,
    )
    return QMatEntry(
        reference=ref,
        hamiltonian=ham,
        tags=["test", "silicon"],
    )
