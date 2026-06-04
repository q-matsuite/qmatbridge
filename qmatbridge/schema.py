"""QMatBridge canonical schema — v0.1.

Neutral intermediate representation (NIR) connecting classical materials
databases to first-quantized Hamiltonians for quantum simulation research.

All dataclasses are intentionally dependency-free.  Adapters and exporters
import from this module::

    from qmatbridge.schema import QMatEntry, MaterialReference, ...

Class hierarchy (leaf → root):

    ExternalIdentifier
    SourceProvenance        ← ExternalIdentifier
    LatticeMetadata
    StructureMetadata       ← LatticeMetadata
    BasisMetadata
    TermMetadata
    OracleMetadata          ← TermMetadata
    ExportMetadata
    MaterialReference       ← SourceProvenance, StructureMetadata
    HamiltonianMetadata     ← BasisMetadata, TermMetadata, OracleMetadata
    QMatEntry               ← MaterialReference, HamiltonianMetadata, ExportMetadata
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

__all__ = [
    "ExternalIdentifier",
    "SourceProvenance",
    "LatticeMetadata",
    "StructureMetadata",
    "BasisMetadata",
    "TermMetadata",
    "OracleMetadata",
    "ExportMetadata",
    "MaterialReference",
    "HamiltonianMetadata",
    "QMatEntry",
]


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


@dataclass
class ExternalIdentifier:
    """A single identifier in one external system.

    Used to record the upstream database record this entry was derived from,
    as well as any cross-references (e.g. ICSD entry, journal DOI).

    Attributes:
        source:     Canonical short name for the database or registry.
                    Examples: ``"materials_project"``, ``"aflow"``,
                    ``"icsd"``, ``"cod"``, ``"doi"``.
        identifier: The database-native ID string.
                    Examples: ``"mp-149"``, ``"10.1103/PhysRevLett.77.3865"``.
        url:        Optional direct URL to the record.
        metadata:   Adapter-specific extra fields.
    """

    source: str
    identifier: str
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceProvenance:
    """Full provenance record for one QMatEntry.

    Captures which database the material came from, what DFT settings were
    used, and when the data was retrieved.  The ``primary`` identifier is the
    canonical source used for the canonical hash; ``additional_ids`` record
    any known cross-references.

    Attributes:
        primary:          Canonical upstream identifier (required).
        additional_ids:   Other known identifiers for the same material.
        functional:       DFT exchange-correlation functional.
                          Examples: ``"PBE"``, ``"PBE+U"``, ``"HSE06"``.
        pseudopotential:  Pseudopotential family.
                          Examples: ``"PAW_PBE"``, ``"ONCV_PBE"``, ``"SG15"``.
        code:             Electronic-structure code used.
                          Examples: ``"VASP"``, ``"QE"``, ``"ABINIT"``.
        code_version:     Version string of the DFT code.
        retrieved_at:     ISO 8601 datetime when the record was fetched.
        metadata:         Adapter-specific extra fields.
    """

    primary: ExternalIdentifier
    additional_ids: list[ExternalIdentifier] = field(default_factory=list)
    functional: str | None = None
    pseudopotential: str | None = None
    code: str | None = None
    code_version: str | None = None
    retrieved_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Crystal structure
# ---------------------------------------------------------------------------


@dataclass
class LatticeMetadata:
    """Bravais lattice and crystallographic parameters.

    Lattice parameters follow crystallographic convention: lengths in
    Ångström, angles in degrees.

    Attributes:
        a, b, c:            Lattice parameter lengths in Å.
        alpha, beta, gamma: Inter-axial angles in degrees.
        spacegroup_number:  International spacegroup number (1–230).
        spacegroup_symbol:  Hermann-Mauguin symbol, e.g. ``"Fd-3m"``.
        crystal_system:     One of ``"triclinic"``, ``"monoclinic"``,
                            ``"orthorhombic"``, ``"tetragonal"``,
                            ``"trigonal"``, ``"hexagonal"``, ``"cubic"``.
        volume_ang3:        Unit cell volume in Å³.
        metadata:           Extra crystallographic fields.
    """

    a: float
    b: float
    c: float
    alpha: float
    beta: float
    gamma: float
    spacegroup_number: int | None = None
    spacegroup_symbol: str | None = None
    crystal_system: str | None = None
    volume_ang3: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StructureMetadata:
    """Chemical and geometric identity of the crystal structure.

    Attributes:
        formula_reduced:    Reduced formula, e.g. ``"Si"``, ``"GaAs"``.
        formula_unit_cell:  Unit-cell formula, e.g. ``"Si2"``.
        num_sites:          Number of atomic sites in the simulation cell.
        species:            Ordered list of element symbols per site,
                            e.g. ``["Si", "Si"]``.
        lattice:            Bravais lattice and crystallographic parameters.
        is_periodic:        Whether the structure is treated as periodic.
                            ``False`` for molecules or clusters.
        metadata:           Extra structure-level fields.
    """

    formula_reduced: str
    formula_unit_cell: str
    num_sites: int
    species: list[str]
    lattice: LatticeMetadata
    is_periodic: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Basis set
# ---------------------------------------------------------------------------


@dataclass
class BasisMetadata:
    """Basis-set specification for the Hamiltonian.

    Plane-wave fields are populated for ``type="plane_wave"``; Gaussian/LCAO
    fields for ``type`` in ``{"gaussian", "lcao"}``.  Unused fields are
    left as ``None``.

    Attributes:
        type:                Basis type identifier. Recognised values:
                             ``"plane_wave"``, ``"gaussian"``, ``"lcao"``,
                             ``"real_space"``.
        cutoff_energy_ev:    Plane-wave kinetic-energy cutoff in eV.
        num_plane_waves:     Number of plane waves at the cutoff (|G|² ≤ Ecut).
        grid_dimensions:     Real-space grid dimensions (Nx, Ny, Nz).
        basis_set_name:      Gaussian or LCAO basis set name,
                             e.g. ``"cc-pVTZ"``, ``"STO-3G"``.
        num_basis_functions: Total number of basis functions.
        metadata:            Extra basis-specific fields.
    """

    type: str
    cutoff_energy_ev: float | None = None
    num_plane_waves: int | None = None
    grid_dimensions: tuple[int, int, int] | None = None
    basis_set_name: str | None = None
    num_basis_functions: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Hamiltonian terms
# ---------------------------------------------------------------------------


@dataclass
class TermMetadata:
    """Metadata for one physical or decomposition term in the Hamiltonian.

    A term may be a physical contribution (kinetic, electron-electron Coulomb,
    electron-nuclear Coulomb, exchange-correlation) or a block in an LCU /
    qubitization decomposition.

    Attributes:
        name:                  Short identifier. Physical examples:
                               ``"kinetic"``, ``"electron_electron"``,
                               ``"electron_nuclear"``, ``"xc"``.
                               Decomposition examples: ``"lcu_block_0"``.
        lambda_one_norm:       L1 norm (LCU coefficient sum) for this term,
                               in Hartree.
        lambda_spectral:       Spectral norm of this term, in Hartree.
        num_lcu_terms:         Number of LCU sub-terms in this block.
        truncation_threshold:  Coefficient magnitude below which terms are
                               dropped, in Hartree.
        coefficient_labels:    Ordered labels for individual LCU coefficients
                               within this term, e.g. ``["T_G0", "T_G1"]``.
                               Empty when coefficient-level detail is not
                               stored.
        implementation_notes:  Free-text notes about how this term is
                               implemented or accessed — e.g. which FFT/QROM
                               circuit is used, or whether it exploits
                               symmetry.
        metadata:              Extra per-term fields.
    """

    name: str
    lambda_one_norm: float | None = None
    lambda_spectral: float | None = None
    num_lcu_terms: int | None = None
    truncation_threshold: float | None = None
    coefficient_labels: list[str] = field(default_factory=list)
    implementation_notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Oracle / decomposition
# ---------------------------------------------------------------------------


@dataclass
class OracleMetadata:
    """Oracle and decomposition parameters for fault-tolerant Hamiltonian simulation.

    Captures the quantities needed for T-gate and qubit resource estimates:
    the LCU 1-norm λ, the number of terms, and per-term breakdowns for the
    dominant physical contributions.

    Attributes:
        method:               Decomposition / simulation strategy. Examples:
                              ``"lcu"``, ``"qubitization"``,
                              ``"sparse"``, ``"tensor_hypercontraction"``.
        lambda_total:         Total LCU 1-norm λ (sum over all terms), in Ha.
        num_lcu_terms:        Total number of terms in the LCU decomposition.
        eta:                  Target energy accuracy ε in Hartree (used to set
                              rotation precision and truncation thresholds).
        delta_e:              Target energy precision for the full simulation,
                              in Hartree.
        num_bits_state:       Number of qubits for the electronic state
                              register.
        num_bits_rot:         Number of bits for rotation synthesis (b_r).
        terms:                Per-physical-term LCU breakdown; see
                              :class:`TermMetadata`.
        oracle_type:          Circuit-level oracle pattern being targeted.
                              Examples: ``"SELECT"``, ``"PREPARE"``,
                              ``"SELECT_PREPARE"``, ``"QROM"``,
                              ``"sparse_access"``.
        index_encoding:       How term indices are encoded in qubits.
                              Examples: ``"binary"``, ``"unary"``,
                              ``"one_hot"``.  ``None`` when not yet
                              determined.
        coefficient_sampling: Notes on how the PREPARE oracle loads LCU
                              coefficients — e.g. ``"alias_sampling"``,
                              ``"QROM_direct"``, ``"uniform_superposition"``.
        complexity:           Annotated complexity quantities for this oracle.
                              Keys are descriptive strings; values are numeric
                              counts or symbolic expressions.  Examples::

                                  {
                                    "T_count_formula": "O(lambda/delta_e)",
                                    "toffoli_count": 123456,
                                    "ancilla_qubits": 42,
                                  }

        metadata:             Extra oracle-level fields.
    """

    method: str
    lambda_total: float | None = None
    num_lcu_terms: int | None = None
    eta: float | None = None
    delta_e: float | None = None
    num_bits_state: int | None = None
    num_bits_rot: int | None = None
    terms: list[TermMetadata] = field(default_factory=list)
    oracle_type: str | None = None
    index_encoding: str | None = None
    coefficient_sampling: str | None = None
    complexity: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Export records
# ---------------------------------------------------------------------------


@dataclass
class ExportMetadata:
    """Record of one downstream export generated from a QMatEntry.

    Populated by exporter modules when they produce an artifact for a
    downstream quantum framework.

    Attributes:
        framework:      Target framework name.
                        Examples: ``"openfermion"``, ``"pennylane"``,
                        ``"qualtran"``, ``"pyliqtr"``, ``"qiskit"``.
        format:         Output format / object type.
                        Examples: ``"InteractionOperator"``,
                        ``"sparse_matrix"``, ``"lcu_coefficients"``,
                        ``"FermionOperator"``.
        target_name:    Human-readable label for this export target, used
                        when multiple exports target the same framework with
                        different formats or options.
                        Example: ``"openfermion_sparse_8e"``.
        status:         Lifecycle status of the export.  One of
                        ``"pending"``, ``"complete"``, ``"failed"``.
                        Default: ``"pending"``.
        version:        Version of the target framework used.
        exported_at:    ISO 8601 datetime of the export.
        artifact_path:  Filesystem or object-store path to the artifact.
        metadata:       Extra export-level fields.
    """

    framework: str
    format: str
    target_name: str | None = None
    status: str = "pending"
    version: str | None = None
    exported_at: str | None = None
    artifact_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level reference and Hamiltonian objects
# ---------------------------------------------------------------------------


@dataclass
class MaterialReference:
    """Provenance and structural identity of a material.

    Combines the upstream-database provenance with the crystal-structure
    description so that any downstream component can reconstruct where the
    material came from and what it looks like geometrically.

    Attributes:
        provenance: Upstream-database provenance (source, functional, code).
        structure:  Crystal-structure description (formula, lattice, sites).
    """

    provenance: SourceProvenance
    structure: StructureMetadata


@dataclass
class HamiltonianMetadata:
    """Full specification of the Hamiltonian derived from a DFT calculation.

    Ties together the basis-set choice, the physical-term breakdown, and the
    oracle-level decomposition parameters needed for fault-tolerant resource
    estimation.

    Attributes:
        num_electrons:  Number of electrons in the simulation cell (η).
        spin_polarized: Whether spin-up and spin-down are treated separately.
        basis:          Basis-set specification; see :class:`BasisMetadata`.
        num_bands:      Number of bands / orbitals included in the
                        truncated Hamiltonian. ``None`` means all bands
                        up to the cutoff are included.
        terms:          Physical-term breakdown; see :class:`TermMetadata`.
        oracle:         Oracle / decomposition metadata for fault-tolerant
                        algorithms; see :class:`OracleMetadata`.
                        ``None`` until an oracle decomposition is computed.
        metadata:       Extra Hamiltonian-level fields.
    """

    num_electrons: int
    spin_polarized: bool
    basis: BasisMetadata
    num_bands: int | None = None
    terms: list[TermMetadata] = field(default_factory=list)
    oracle: OracleMetadata | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Root entry
# ---------------------------------------------------------------------------


@dataclass
class QMatEntry:
    """Top-level neutral intermediate representation.

    The canonical record that adapters produce and exporters consume.
    Every entry is serializable to a plain dictionary and carries a
    deterministic canonical hash over its physically meaningful fields.

    Attributes:
        reference:  Material provenance and structure.
        hamiltonian: Hamiltonian parameters (basis, terms, oracle).
        exports:    Downstream export records attached to this entry.
        tags:       Free-form labels for filtering and grouping.
        schema_version: Version of the QMatBridge schema this entry
                        conforms to.
    """

    reference: MaterialReference
    hamiltonian: HamiltonianMetadata
    exports: list[ExportMetadata] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    schema_version: str = "0.1"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full entry to a JSON-serializable plain dictionary."""
        return asdict(self)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def canonical_hash(self) -> str:
        """SHA-256 digest over the physically meaningful fields of this entry.

        The hash is stable across ``metadata`` / ``extra`` dict changes,
        tag edits, and export record additions.  It changes when any field
        that alters the physics of the Hamiltonian is modified.

        Fields included: upstream source + identifier, reduced formula,
        spacegroup, electron count, spin polarization, basis type, cutoff
        energy, number of bands, and oracle eta.
        """
        prov = self.reference.provenance
        struct = self.reference.structure
        ham = self.hamiltonian

        core: dict[str, Any] = {
            "source": prov.primary.source,
            "identifier": prov.primary.identifier,
            "functional": prov.functional,
            "formula_reduced": struct.formula_reduced,
            "spacegroup_number": struct.lattice.spacegroup_number,
            "num_electrons": ham.num_electrons,
            "spin_polarized": ham.spin_polarized,
            "basis_type": ham.basis.type,
            "cutoff_energy_ev": ham.basis.cutoff_energy_ev,
            "num_bands": ham.num_bands,
            "oracle_eta": ham.oracle.eta if ham.oracle is not None else None,
        }
        blob = json.dumps(core, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()

    def __repr__(self) -> str:
        prov = self.reference.provenance.primary
        ham = self.hamiltonian
        return (
            f"QMatEntry("
            f"formula={self.reference.structure.formula_reduced!r}, "
            f"source={prov.source!r}, "
            f"id={prov.identifier!r}, "
            f"electrons={ham.num_electrons}, "
            f"basis={ham.basis.type!r}"
            f")"
        )
