"""Reproducibility checks for QMatBridge entries.

This example shows two important behaviors of `QMatEntry.canonical_hash()`:
1. Stability: equivalent entries produce the same hash.
2. Sensitivity: changing a physical field changes the hash.

Run:
    python examples/reproducibility_checks.py
"""

from __future__ import annotations

import copy
from pathlib import Path

from qmatbridge.io import write_entry_json
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


def make_reference_entry() -> QMatEntry:
    """Construct a compact but realistic silicon entry."""
    provenance = SourceProvenance(
        primary=ExternalIdentifier(
            source="materials_project",
            identifier="mp-149",
            url="https://materialsproject.org/materials/mp-149",
        ),
        functional="PBE",
        pseudopotential="PAW_PBE",
        code="VASP",
        code_version="6.3.2",
        retrieved_at="2026-06-04T00:00:00Z",
    )

    structure = StructureMetadata(
        formula_reduced="Si",
        formula_unit_cell="Si2",
        num_sites=2,
        species=["Si", "Si"],
        lattice=LatticeMetadata(
            a=3.867,
            b=3.867,
            c=3.867,
            alpha=60.0,
            beta=60.0,
            gamma=60.0,
            spacegroup_number=227,
            spacegroup_symbol="Fd-3m",
        ),
    )

    hamiltonian = HamiltonianMetadata(
        num_electrons=8,
        spin_polarized=False,
        basis=BasisMetadata(
            type="plane_wave",
            cutoff_energy_ev=520.0,
            num_plane_waves=1849,
        ),
        num_bands=16,
    )

    return QMatEntry(
        reference=MaterialReference(provenance=provenance, structure=structure),
        hamiltonian=hamiltonian,
        tags=["silicon", "reproducibility"],
    )


def main() -> None:
    entry_a = make_reference_entry()
    entry_b = copy.deepcopy(entry_a)

    hash_a = entry_a.canonical_hash()
    hash_b = entry_b.canonical_hash()
    stable = hash_a == hash_b

    # Modify one physical parameter and recompute.
    entry_c = copy.deepcopy(entry_a)
    entry_c.hamiltonian.basis.cutoff_energy_ev = 530.0
    hash_c = entry_c.canonical_hash()
    sensitive = hash_a != hash_c

    print("=== Canonical Hash Reproducibility ===")
    print(f"hash(entry_a): {hash_a}")
    print(f"hash(entry_b): {hash_b}")
    print(f"stable for identical entries: {stable}")

    print("\n=== Canonical Hash Sensitivity ===")
    print("changed field: hamiltonian.basis.cutoff_energy_ev (520.0 -> 530.0)")
    print(f"hash(entry_c): {hash_c}")
    print(f"changed after physical edit: {sensitive}")

    out = Path(__file__).parent / "outputs" / "reproducibility_entry.json"
    written = write_entry_json(entry_a, out)
    print(f"\nWrote baseline entry JSON: {written}")


if __name__ == "__main__":
    main()
