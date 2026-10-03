"""OQMD (Open Quantum Materials Database) adapter for QMatBridge — stub / v0.3 target.

This module defines the interface that will bridge the Open Quantum Materials
Database (https://oqmd.org) to QMatBridge's neutral intermediate representation.

OQMD overview
-------------
OQMD contains ~1 million DFT-relaxed inorganic structures computed with VASP
and the PBE functional.  It provides systematic coverage of binary and ternary
phase diagrams and is publicly accessible via a REST API without an API key.
Entry IDs are integers (e.g. ``1234``) or prefixed strings (``"oqmd-1234"``).

Current status
--------------
**Stub only.**  ``build_material_reference_from_oqmd`` constructs a
``MaterialReference`` from a known OQMD entry ID and any structural metadata
already in hand, without making a network call.
``fetch_structure_metadata_from_oqmd`` and ``fetch_hamiltonian_metadata_from_oqmd``
raise ``NotImplementedError`` — they mark the seam where the ``qmpy-rester``
integration will be inserted in v0.3.

Planned v0.3 work
-----------------
* REST client integration via ``qmpy-rester`` (or direct ``httpx`` calls to
  the public OQMD REST API at ``https://oqmd.org/oqmdapi/``)
* Structure fetch: lattice, sites, spacegroup from ``/oqmdapi/entry/<id>``
* DFT settings extraction: VASP ENCUT, k-point density from calculation record
* Plane-wave count utility shared with the Materials Project adapter

Dependencies
------------
The stub functions in this module require **no external dependencies**.
Once the live fetchers are implemented, install the optional extra::

    pip install qmatbridge[oqmd]

which adds ``qmpy-rester``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from qmatbridge.schema import (
    ExternalIdentifier,
    LatticeMetadata,
    MaterialReference,
    SourceProvenance,
    StructureMetadata,
)

__all__ = [
    "OQMDAdapterConfig",
    "build_material_reference_from_oqmd",
    "fetch_structure_metadata_from_oqmd",
    "fetch_hamiltonian_metadata_from_oqmd",
]

# ---------------------------------------------------------------------------
# Adapter configuration
# ---------------------------------------------------------------------------

_LATTICE_UNKNOWN: float = 0.0

_OQMD_REST_BASE = "https://oqmd.org/oqmdapi"


@dataclass
class OQMDAdapterConfig:
    """Configuration for the OQMD REST adapter.

    OQMD's public REST API requires no authentication.  Rate limiting is
    enforced server-side; use ``timeout_s`` and ``retry`` to manage it.

    Attributes:
        endpoint:   Base URL for the OQMD REST API.
        timeout_s:  HTTP request timeout in seconds.
        max_sites:  If set, skip structures with more than this many sites.
        metadata:   Arbitrary extra config passed through to adapters.
    """

    endpoint: str = _OQMD_REST_BASE
    timeout_s: float = 30.0
    max_sites: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ID normalisation helpers
# ---------------------------------------------------------------------------

def _normalise_entry_id(entry_id: str | int) -> tuple[str, str]:
    """Return ``(canonical_id, url)`` for an OQMD entry.

    Accepts bare integers (``1234``), integer strings (``"1234"``), and
    prefixed strings (``"oqmd-1234"``).  Always returns the prefixed form
    as the canonical identifier stored in ``ExternalIdentifier.identifier``.
    """
    raw = str(entry_id).strip()
    numeric = raw.removeprefix("oqmd-")
    canonical = f"oqmd-{numeric}"
    url = f"https://oqmd.org/materials/entry/{numeric}"
    return canonical, url


# ---------------------------------------------------------------------------
# Stub builder — no API call required
# ---------------------------------------------------------------------------

def build_material_reference_from_oqmd(
    entry_id: str | int,
    formula: str | None = None,
    *,
    formula_unit_cell: str | None = None,
    num_sites: int = 0,
    species: list[str] | None = None,
    spacegroup_number: int | None = None,
    spacegroup_symbol: str | None = None,
    crystal_system: str | None = None,
    functional: str = "PBE",
    pseudopotential: str = "PAW_PBE",
    code: str = "VASP",
    code_version: str | None = None,
    retrieved_at: str | None = None,
    config: OQMDAdapterConfig | None = None,
) -> MaterialReference:
    """Build a ``MaterialReference`` from a known OQMD entry ID.

    This function requires **no network call**.  It constructs a fully
    valid ``MaterialReference`` from the supplied arguments, with lattice
    parameters set to ``0.0`` (placeholder) for fields that require a live
    ``fetch_structure_metadata_from_oqmd`` call to populate.

    Args:
        entry_id:           OQMD entry ID — bare integer (``1234``),
                            integer string (``"1234"``), or prefixed
                            (``"oqmd-1234"``).  Stored in canonical
                            ``"oqmd-<n>"`` form.
        formula:            Reduced formula, e.g. ``"Si"``.  Defaults to
                            the canonical entry ID string if not given.
        formula_unit_cell:  Unit-cell formula.  Defaults to ``formula``.
        num_sites:          Site count; use ``0`` when unknown.
        species:            Ordered element symbols per site.
        spacegroup_number:  International spacegroup number (1–230).
        spacegroup_symbol:  Hermann-Mauguin symbol.
        crystal_system:     Crystal system string, e.g. ``"cubic"``.
        functional:         XC functional.  Default: ``"PBE"``.
        pseudopotential:    Pseudopotential family.  Default: ``"PAW_PBE"``.
        code:               Electronic-structure code.  Default: ``"VASP"``.
        code_version:       Code version string.
        retrieved_at:       ISO 8601 datetime string.
        config:             Adapter configuration.  Uses defaults if ``None``.

    Returns:
        A ``MaterialReference`` whose ``structure.lattice`` contains
        placeholder values (``0.0``).  Replace it with the result of
        ``fetch_structure_metadata_from_oqmd`` once available.

    Example::

        from qmatbridge.adapters.oqmd import build_material_reference_from_oqmd

        ref = build_material_reference_from_oqmd(
            1214579,
            formula="Si",
            spacegroup_number=227,
            spacegroup_symbol="Fd-3m",
            crystal_system="cubic",
        )
        print(ref.provenance.primary.identifier)  # "oqmd-1214579"
        print(ref.provenance.primary.url)         # "https://oqmd.org/..."
    """
    _config = config or OQMDAdapterConfig()
    canonical_id, url = _normalise_entry_id(entry_id)

    formula_reduced = formula or canonical_id
    formula_uc = formula_unit_cell or formula_reduced

    provenance = SourceProvenance(
        primary=ExternalIdentifier(
            source="oqmd",
            identifier=canonical_id,
            url=url,
        ),
        functional=functional,
        pseudopotential=pseudopotential,
        code=code,
        code_version=code_version,
        retrieved_at=retrieved_at,
        metadata={"endpoint": _config.endpoint},
    )

    lattice = LatticeMetadata(
        a=_LATTICE_UNKNOWN,
        b=_LATTICE_UNKNOWN,
        c=_LATTICE_UNKNOWN,
        alpha=_LATTICE_UNKNOWN,
        beta=_LATTICE_UNKNOWN,
        gamma=_LATTICE_UNKNOWN,
        spacegroup_number=spacegroup_number,
        spacegroup_symbol=spacegroup_symbol,
        crystal_system=crystal_system,
        metadata={"_placeholder": True},
    )

    structure = StructureMetadata(
        formula_reduced=formula_reduced,
        formula_unit_cell=formula_uc,
        num_sites=num_sites,
        species=species or [],
        lattice=lattice,
        is_periodic=True,
        metadata={"_placeholder": True},
    )

    return MaterialReference(provenance=provenance, structure=structure)


# ---------------------------------------------------------------------------
# Live fetcher stubs — require qmpy-rester (v0.3 implementation target)
# ---------------------------------------------------------------------------

def fetch_structure_metadata_from_oqmd(
    entry_id: str | int,
    config: OQMDAdapterConfig | None = None,
) -> StructureMetadata:
    """Fetch crystal structure from the OQMD REST API.

    Retrieves lattice parameters, site positions, and spacegroup for the
    given entry and returns a fully-populated ``StructureMetadata``.

    .. note::
        **Not yet implemented.**  This is the primary v0.3 target for the
        OQMD adapter.  The OQMD REST API requires no API key.

    Args:
        entry_id: OQMD entry ID (integer, integer string, or ``"oqmd-<n>"``).
        config:   Adapter configuration.

    Returns:
        ``StructureMetadata`` with all fields populated from the OQMD record.

    Raises:
        NotImplementedError: Always, until v0.3 is implemented.
    """
    raise NotImplementedError(
        "fetch_structure_metadata_from_oqmd is not yet implemented.\n"
        "This function is the primary target for the v0.3 OQMD adapter.\n"
        "Track progress at: https://github.com/QMatBridge/qmatbridge/issues"
    )


def fetch_hamiltonian_metadata_from_oqmd(
    entry_id: str | int,
    config: OQMDAdapterConfig | None = None,
) -> Any:
    """Fetch DFT Hamiltonian parameters from the OQMD REST API.

    Retrieves VASP calculation settings (ENCUT, k-point density, POTCAR
    family) and packages them into a ``HamiltonianMetadata`` object.

    .. note::
        **Not yet implemented.**  Planned alongside
        ``fetch_structure_metadata_from_oqmd`` in v0.3.

    Args:
        entry_id: OQMD entry ID.
        config:   Adapter configuration.

    Returns:
        ``HamiltonianMetadata`` populated from the OQMD calculation record.

    Raises:
        NotImplementedError: Always, until v0.3 is implemented.
    """
    raise NotImplementedError(
        "fetch_hamiltonian_metadata_from_oqmd is not yet implemented.\n"
        "This function is the primary target for the v0.3 OQMD adapter.\n"
        "Track progress at: https://github.com/QMatBridge/qmatbridge/issues"
    )
