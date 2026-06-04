"""Realistic QMatEntry for bulk silicon (mp-149) in a plane-wave basis.

Demonstrates the full v0.1 schema for a periodic material with:
  - Materials Project provenance (PBE / PAW_PBE / VASP)
  - Diamond-cubic crystal structure (Fd-3m, spacegroup 227)
  - Plane-wave basis at 520 eV cutoff
  - Physical Hamiltonian term breakdown (kinetic, e-e, e-n)
  - LCU oracle metadata consistent with first-quantized plane-wave methods
    (λ values are illustrative; see Babbush et al. 2019 for benchmarks)

Run this script directly to write silicon_entry.json alongside it::

    python examples/minimal_entry.py

No external dependencies required — only the qmatbridge core.
"""

from __future__ import annotations

from pathlib import Path

from qmatbridge.io import write_entry_json
from qmatbridge.schema import (
    BasisMetadata,
    ExternalIdentifier,
    HamiltonianMetadata,
    LatticeMetadata,
    MaterialReference,
    OracleMetadata,
    QMatEntry,
    SourceProvenance,
    StructureMetadata,
    TermMetadata,
)


def make_silicon_entry() -> QMatEntry:
    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------
    mp_id = ExternalIdentifier(
        source="materials_project",
        identifier="mp-149",
        url="https://materialsproject.org/materials/mp-149",
        metadata={"mp_task_id": "mp-1040685", "task_type": "GGA Static"},
    )
    icsd_ref = ExternalIdentifier(
        source="icsd",
        identifier="51688",
    )
    provenance = SourceProvenance(
        primary=mp_id,
        additional_ids=[icsd_ref],
        functional="PBE",
        pseudopotential="PAW_PBE",
        code="VASP",
        code_version="6.3.2",
        retrieved_at="2026-06-03T00:00:00Z",
        metadata={"encut_vasp": 520.0, "kpoints_mesh": "8x8x8"},
    )

    # ------------------------------------------------------------------
    # Crystal structure — Si diamond cubic primitive cell
    # 2-atom primitive cell: a = 3.867 Å (PBE relaxed)
    # ------------------------------------------------------------------
    lattice = LatticeMetadata(
        a=3.867, b=3.867, c=3.867,
        alpha=60.0, beta=60.0, gamma=60.0,
        spacegroup_number=227,
        spacegroup_symbol="Fd-3m",
        crystal_system="cubic",
        volume_ang3=45.78,
    )
    structure = StructureMetadata(
        formula_reduced="Si",
        formula_unit_cell="Si2",
        num_sites=2,
        species=["Si", "Si"],
        lattice=lattice,
        is_periodic=True,
        metadata={"wyckoff_positions": ["8a", "8a"], "point_group": "m-3m"},
    )

    reference = MaterialReference(provenance=provenance, structure=structure)

    # ------------------------------------------------------------------
    # Basis — plane-wave at 520 eV
    # N ≈ (Ecut / (ħ²/2m)) * V / (2π)³ — here we use the literature value
    # for Si at 520 eV: ~1800 plane waves per spin channel
    # ------------------------------------------------------------------
    basis = BasisMetadata(
        type="plane_wave",
        cutoff_energy_ev=520.0,
        num_plane_waves=1849,
        metadata={"gamma_centered": True, "fft_grid": [36, 36, 36]},
    )

    # ------------------------------------------------------------------
    # Physical Hamiltonian terms
    # λ values (Ha) are approximate, representative of a small-cell calc.
    # Kinetic: dominant; e-e Coulomb and e-n typically comparable.
    # ------------------------------------------------------------------
    terms = [
        TermMetadata(
            name="kinetic",
            lambda_one_norm=124.3,
            lambda_spectral=91.7,
            num_lcu_terms=1849,
            truncation_threshold=1e-5,
        ),
        TermMetadata(
            name="electron_electron",
            lambda_one_norm=89.4,
            lambda_spectral=64.2,
            num_lcu_terms=1849 * 1849 // 2,
            truncation_threshold=1e-5,
        ),
        TermMetadata(
            name="electron_nuclear",
            lambda_one_norm=102.1,
            lambda_spectral=78.6,
            num_lcu_terms=1849 * 2,
            truncation_threshold=1e-5,
        ),
    ]

    # ------------------------------------------------------------------
    # Oracle metadata — first-quantized LCU (plane-wave basis)
    # Following the qubitization approach of Babbush et al. (2019).
    # λ_total ≈ λ_T + λ_U + λ_V in their notation.
    # ------------------------------------------------------------------
    oracle = OracleMetadata(
        method="lcu",
        lambda_total=315.8,         # Ha — sum of physical term norms
        num_lcu_terms=3_430_000,    # approximate for this basis size
        eta=1e-3,                   # 1 mHa target accuracy
        delta_e=1.6e-3,             # ~1 kcal/mol (chemical accuracy)
        num_bits_state=11,          # ceil(log2(N)) for N=1849 plane waves
        num_bits_rot=20,
        terms=terms,
        metadata={"reference": "Babbush et al., npj Quantum Information (2019)"},
    )

    # ------------------------------------------------------------------
    # Hamiltonian
    # ------------------------------------------------------------------
    hamiltonian = HamiltonianMetadata(
        num_electrons=8,            # valence electrons in primitive cell
        spin_polarized=False,
        basis=basis,
        num_bands=16,               # 2× electrons — standard starting point
        terms=terms,
        oracle=oracle,
        metadata={"total_energy_ev": -10.843, "bandgap_ev": 0.61},
    )

    return QMatEntry(
        reference=reference,
        hamiltonian=hamiltonian,
        tags=["silicon", "plane_wave", "benchmark", "lcu"],
    )


if __name__ == "__main__":
    entry = make_silicon_entry()

    print("=== QMatEntry ===")
    print(entry)
    print(f"\nSchema version : {entry.schema_version}")
    print(f"Canonical hash : {entry.canonical_hash()}")
    print(f"Tags           : {entry.tags}")

    ref = entry.reference
    ham = entry.hamiltonian

    print("\n=== Provenance ===")
    prov = ref.provenance
    print(f"  Source       : {prov.primary.source} / {prov.primary.identifier}")
    print(f"  Functional   : {prov.functional}  |  PP: {prov.pseudopotential}")
    print(f"  Code         : {prov.code} {prov.code_version}")
    print(f"  Retrieved    : {prov.retrieved_at}")
    cross = [i.source + ":" + i.identifier for i in prov.additional_ids]
    print(f"  Cross-refs   : {cross}")

    print("\n=== Crystal structure ===")
    s = ref.structure
    lat = s.lattice
    print(f"  Formula      : {s.formula_reduced}  ({s.formula_unit_cell})")
    print(f"  Sites        : {s.num_sites}  {s.species}")
    print(f"  Spacegroup   : {lat.spacegroup_number} ({lat.spacegroup_symbol})")
    print(f"  Lattice a    : {lat.a} Å   Volume: {lat.volume_ang3} Å³")

    print("\n=== Basis ===")
    b = ham.basis
    print(f"  Type         : {b.type}")
    print(f"  Cutoff       : {b.cutoff_energy_ev} eV")
    print(f"  Plane waves  : {b.num_plane_waves}")

    print("\n=== Hamiltonian ===")
    sp = ham.spin_polarized
    print(f"  Electrons    : {ham.num_electrons}  (spin-polarized: {sp})")
    print(f"  Bands        : {ham.num_bands}")

    print("\n=== Physical terms ===")
    for t in ham.terms:
        print(
            f"  {t.name:<22} λ₁={t.lambda_one_norm:>7.1f} Ha"
            f"   n_terms={t.num_lcu_terms}"
        )

    print("\n=== Oracle (LCU) ===")
    o = ham.oracle
    if o:
        print(f"  Method       : {o.method}")
        print(f"  λ_total      : {o.lambda_total} Ha")
        print(f"  LCU terms    : {o.num_lcu_terms:,}")
        print(f"  η (accuracy) : {o.eta} Ha")
        print(f"  Δε target    : {o.delta_e} Ha")
        print(f"  State qubits : {o.num_bits_state}")
        print(f"  Rotation bits: {o.num_bits_rot}")

    # ------------------------------------------------------------------
    # JSON export
    # ------------------------------------------------------------------
    out = Path(__file__).parent / "silicon_entry.json"
    written = write_entry_json(entry, out)
    print(f"\nWrote {written.stat().st_size:,} bytes → {written}")
