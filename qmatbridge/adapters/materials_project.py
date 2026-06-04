"""Materials Project adapter for QMatBridge — stub / v0.2 target.

This module defines the interface that will bridge the Materials Project
database (https://materialsproject.org) to QMatBridge's neutral intermediate
representation.

Current status
--------------
**Stub only.**  ``build_material_reference_from_mp`` constructs a
``MaterialReference`` from a known MP material ID and any structural
metadata already in hand, without making a network call.
``fetch_structure_metadata_from_mp`` and ``fetch_hamiltonian_metadata_from_mp``
raise ``NotImplementedError`` — they mark the seam where the full
``mp-api`` integration will be inserted in v0.2.

Planned v0.2 work
-----------------
* Full ``mp-api`` client integration behind the ``[mp]`` optional extra
* Plane-wave basis truncation utilities (``num_plane_waves`` from Ecut + V)
* Coulomb operator in reciprocal space (electron–electron, electron–nuclear)
* Extraction of VASP INCAR/KPOINTS settings into ``SourceProvenance.metadata``

Dependencies
------------
The stub functions in this module require **no external dependencies**.
Once the live fetchers are implemented, install the optional extra::

    pip install qmatbridge[mp]

which adds ``mp-api`` and ``pymatgen``.
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
    "MPAdapterConfig",
    "build_material_reference_from_mp",
    "fetch_structure_metadata_from_mp",
    "fetch_hamiltonian_metadata_from_mp",
]

# ---------------------------------------------------------------------------
# Adapter configuration
# ---------------------------------------------------------------------------

# Sentinel used for lattice parameters not yet fetched from the API.
_LATTICE_UNKNOWN: float = 0.0


@dataclass
class MPAdapterConfig:
    """Configuration for the Materials Project adapter.

    Attributes:
        api_key:      MP API key.  If ``None``, the adapter will look for
                      the ``MP_API_KEY`` environment variable when making
                      live requests.
        endpoint:     Base URL for the MP REST API.
        timeout_s:    HTTP request timeout in seconds.
        max_sites:    If set, skip structures with more than this many sites.
                      Useful for keeping resource estimates tractable.
        fields:       Explicit list of MP document fields to request.
                      Empty list means "use adapter defaults."
        metadata:     Arbitrary extra config passed through to adapters.
    """

    api_key: str | None = None
    endpoint: str = "https://api.materialsproject.org"
    timeout_s: float = 30.0
    max_sites: int | None = None
    fields: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stub builder — no API call required
# ---------------------------------------------------------------------------

def build_material_reference_from_mp(
    material_id: str,
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
    config: MPAdapterConfig | None = None,
) -> MaterialReference:
    """Build a ``MaterialReference`` from a known Materials Project ID.

    This function requires **no network call**.  It constructs a fully
    valid ``MaterialReference`` from the arguments provided, filling
    lattice parameters with ``_LATTICE_UNKNOWN`` (0.0) for fields that
    can only be populated by a live ``fetch_structure_metadata_from_mp``
    call.

    The returned object's provenance is fully populated and its canonical
    hash is stable as long as ``material_id``, ``formula``, and
    ``functional`` are unchanged.

    Args:
        material_id:        MP identifier, e.g. ``"mp-149"``.
        formula:            Reduced chemical formula, e.g. ``"Si"``.
                            Defaults to ``material_id`` if not given.
        formula_unit_cell:  Unit-cell formula, e.g. ``"Si2"``.
                            Defaults to ``formula`` if not given.
        num_sites:          Number of sites in the unit cell.
                            Use ``0`` when unknown.
        species:            Ordered list of element symbols per site.
        spacegroup_number:  International spacegroup number (1–230).
        spacegroup_symbol:  Hermann-Mauguin symbol, e.g. ``"Fd-3m"``.
        crystal_system:     Crystal system string, e.g. ``"cubic"``.
        functional:         DFT XC functional.  Default: ``"PBE"``.
        pseudopotential:    Pseudopotential family.  Default: ``"PAW_PBE"``.
        code:               Electronic-structure code.  Default: ``"VASP"``.
        code_version:       Code version string.
        retrieved_at:       ISO 8601 datetime string.
        config:             Adapter configuration.  Uses defaults if ``None``.

    Returns:
        A ``MaterialReference`` whose ``structure.lattice`` contains
        placeholder values (``0.0``) for the geometric parameters.
        Replace it with the result of ``fetch_structure_metadata_from_mp``
        once available.

    Example::

        from qmatbridge.adapters.materials_project import (
            build_material_reference_from_mp,
        )

        ref = build_material_reference_from_mp(
            "mp-149",
            formula="Si",
            spacegroup_number=227,
            spacegroup_symbol="Fd-3m",
            crystal_system="cubic",
        )
        print(ref.provenance.primary.identifier)   # "mp-149"
        print(ref.structure.lattice.spacegroup_number)  # 227
    """
    _config = config or MPAdapterConfig()

    formula_reduced = formula or material_id
    formula_uc = formula_unit_cell or formula_reduced

    provenance = SourceProvenance(
        primary=ExternalIdentifier(
            source="materials_project",
            identifier=material_id,
            url=f"https://materialsproject.org/materials/{material_id}",
        ),
        functional=functional,
        pseudopotential=pseudopotential,
        code=code,
        code_version=code_version,
        retrieved_at=retrieved_at,
        metadata={"endpoint": _config.endpoint},
    )

    # Lattice parameters are unknown without an API call; placeholders used.
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
# Live fetcher stubs — require mp-api (v0.2 implementation target)
# ---------------------------------------------------------------------------

def fetch_structure_metadata_from_mp(
    material_id: str,
    api_key: str | None = None,
    config: MPAdapterConfig | None = None,
) -> StructureMetadata:
    """Fetch crystal structure from the Materials Project API.

    Retrieves lattice parameters, site positions, spacegroup, and formula
    for the given material and returns a fully-populated
    ``StructureMetadata``.

    .. note::
        **Not yet implemented.**  This is the primary v0.2 target.

    Args:
        material_id: MP identifier, e.g. ``"mp-149"``.
        api_key:     MP API key.  Falls back to ``MPAdapterConfig.api_key``
                     then the ``MP_API_KEY`` environment variable.
        config:      Adapter configuration.

    Returns:
        ``StructureMetadata`` with all fields populated from the MP record.

    Raises:
        NotImplementedError: Always, until v0.2 is implemented.
        ImportError: When ``mp-api`` is not installed (future behaviour).
    """
    raise NotImplementedError(
        "fetch_structure_metadata_from_mp is not yet implemented.\n"
        "This function is the primary target for the v0.2 Materials Project "
        "adapter.\n"
        "Track progress at: https://github.com/rmsreis/qmatbridge/issues"
    )


def fetch_hamiltonian_metadata_from_mp(
    material_id: str,
    api_key: str | None = None,
    config: MPAdapterConfig | None = None,
) -> Any:
    """Fetch DFT Hamiltonian parameters from the Materials Project API.

    Retrieves the VASP calculation parameters (INCAR, KPOINTS, POTCAR info,
    plane-wave cutoff) and packages them into a ``HamiltonianMetadata``
    object.

    .. note::
        **Not yet implemented.**  Planned for v0.2 alongside
        ``fetch_structure_metadata_from_mp``.

    Args:
        material_id: MP identifier, e.g. ``"mp-149"``.
        api_key:     MP API key.
        config:      Adapter configuration.

    Returns:
        ``HamiltonianMetadata`` populated from the MP task document.

    Raises:
        NotImplementedError: Always, until v0.2 is implemented.
        ImportError: When ``mp-api`` is not installed (future behaviour).
    """
    raise NotImplementedError(
        "fetch_hamiltonian_metadata_from_mp is not yet implemented.\n"
        "This function is the primary target for the v0.2 Materials Project "
        "adapter.\n"
        "Track progress at: https://github.com/rmsreis/qmatbridge/issues"
    )
