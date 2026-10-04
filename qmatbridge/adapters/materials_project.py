"""Materials Project adapter for QMatBridge.

Bridges the Materials Project database (https://materialsproject.org) to
QMatBridge's neutral intermediate representation.

Layers
------
1. **Pure converters** — :func:`structure_from_mp_doc` and
   :func:`hamiltonian_from_mp_task_doc` turn plain-dict MP documents into
   schema objects.  No network, no third-party imports; fully unit-testable.
2. **Live fetchers** — :func:`fetch_structure_metadata_from_mp`,
   :func:`fetch_hamiltonian_metadata_from_mp` and :func:`fetch_entry_from_mp`
   query the API through ``mp-api`` (imported lazily) and feed the converters.
3. **Offline builder** — :func:`build_material_reference_from_mp` builds a
   ``MaterialReference`` from known values without any API call.

Status
------
The converters are covered by unit tests against representative documents.
The live fetchers have **not** yet been validated against the production
API in CI; run ``pytest -m integration`` with ``MP_API_KEY`` set to do so.

Dependencies
------------
Layers 1 and 3 need nothing.  Layer 2 needs the optional extra::

    pip install qmatbridge[mp]
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from qmatbridge.basis import num_plane_waves_from_ecut
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

__all__ = [
    "MPAdapterConfig",
    "build_material_reference_from_mp",
    "structure_from_mp_doc",
    "hamiltonian_from_mp_task_doc",
    "functional_from_mp_task_doc",
    "fetch_structure_metadata_from_mp",
    "fetch_hamiltonian_metadata_from_mp",
    "fetch_entry_from_mp",
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
        run_types:    Which calculations to use, in order of preference,
                      matched against the run type of each static task
                      (case-insensitive; ``"GGA"``, ``"GGA+U"``, ``"r2SCAN"``,
                      ``"HSE06"`` ...).  Materials Project stores several
                      static calculations per material, so the choice must be
                      explicit.  Default: the standard PBE workflow.
        fields:       Explicit list of MP document fields to request.
                      Empty list means "use adapter defaults."
        metadata:     Arbitrary extra config passed through to adapters.
    """

    api_key: str | None = None
    endpoint: str = "https://api.materialsproject.org"
    timeout_s: float = 30.0
    max_sites: int | None = None
    run_types: tuple[str, ...] = ("GGA", "GGA+U")
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
# Pure converters — plain-dict MP documents to schema objects
# ---------------------------------------------------------------------------

def _hill_formula(counts: Mapping[str, int]) -> str:
    """Hill-order formula string (C first, H second, then alphabetical)."""
    def key(el: str) -> tuple[int, str]:
        if "C" in counts:
            return (0 if el == "C" else 1 if el == "H" else 2, el)
        return (0, el)

    return "".join(
        f"{el}{counts[el] if counts[el] != 1 else ''}"
        for el in sorted(counts, key=key)
    )


def _reduced_counts(counts: Mapping[str, int]) -> dict[str, int]:
    from functools import reduce
    from math import gcd

    g = reduce(gcd, counts.values())
    return {el: n // g for el, n in counts.items()}


def structure_from_mp_doc(doc: Mapping[str, Any]) -> StructureMetadata:
    """Convert an MP summary document (as a dict) to ``StructureMetadata``.

    Expects ``structure`` in pymatgen ``Structure.as_dict()`` form
    (``lattice`` with ``a, b, c, alpha, beta, gamma``; ``sites`` each with a
    ``species`` list) and, optionally, ``symmetry`` with ``number``,
    ``symbol`` and ``crystal_system``.  Disordered sites are rejected.

    Raises:
        ValueError: If required keys are missing or a site is disordered.
    """
    try:
        struct = doc["structure"]
        lat = struct["lattice"]
        sites = struct["sites"]
        lattice_params = [
            float(lat[k]) for k in ("a", "b", "c", "alpha", "beta", "gamma")
        ]
    except KeyError as exc:
        raise ValueError(f"MP document is missing required key: {exc}") from exc

    species: list[str] = []
    for site in sites:
        occ = site["species"]
        if len(occ) != 1 or float(occ[0].get("occu", 1.0)) != 1.0:
            raise ValueError("disordered / partially occupied sites are not supported")
        species.append(str(occ[0]["element"]))
    if not species:
        raise ValueError("MP structure has no sites")

    counts = Counter(species)
    sym = doc.get("symmetry") or {}
    crystal_system = sym.get("crystal_system")
    lattice = LatticeMetadata(
        a=lattice_params[0], b=lattice_params[1], c=lattice_params[2],
        alpha=lattice_params[3], beta=lattice_params[4], gamma=lattice_params[5],
        spacegroup_number=sym.get("number"),
        spacegroup_symbol=sym.get("symbol"),
        crystal_system=str(crystal_system).lower() if crystal_system else None,
    )
    return StructureMetadata(
        formula_reduced=_hill_formula(_reduced_counts(counts)),
        formula_unit_cell=_hill_formula(counts),
        num_sites=len(species),
        species=species,
        lattice=lattice,
        is_periodic=True,
    )


def hamiltonian_from_mp_task_doc(
    task: Mapping[str, Any], structure: StructureMetadata
) -> HamiltonianMetadata:
    """Convert an MP VASP task document (as a dict) to ``HamiltonianMetadata``.

    Reads ``input.incar.ENCUT`` (eV), ``input.incar.ISPIN`` and
    ``input.parameters.NELECT``.  The plane-wave count is computed from the
    cutoff and ``structure.lattice`` via
    :func:`qmatbridge.basis.num_plane_waves_from_ecut`.

    Raises:
        ValueError: If ``ENCUT`` or ``NELECT`` is absent.
    """
    inp = task.get("input") or {}
    incar = inp.get("incar") or {}
    params = inp.get("parameters") or {}
    if "ENCUT" not in incar:
        raise ValueError("task document has no input.incar.ENCUT")
    if "NELECT" not in params:
        raise ValueError("task document has no input.parameters.NELECT")

    ecut = float(incar["ENCUT"])
    nelect = float(params["NELECT"])
    if nelect != int(nelect):
        raise ValueError(f"non-integer NELECT ({nelect}) is not supported")

    basis = BasisMetadata(
        type="plane_wave",
        cutoff_energy_ev=ecut,
        num_plane_waves=num_plane_waves_from_ecut(structure.lattice, ecut),
    )
    return HamiltonianMetadata(
        num_electrons=int(nelect),
        spin_polarized=int(incar.get("ISPIN", 1)) == 2,
        basis=basis,
        metadata={"source_task_id": task.get("task_id")},
    )


def functional_from_mp_task_doc(task: Mapping[str, Any]) -> str:
    """Name the XC functional of an MP task document (e.g. ``"PBE+U"``).

    Uses ``run_type`` when present (``"GGA"`` → ``"PBE"``, ``"GGA+U"`` →
    ``"PBE+U"``; other run types such as ``"r2SCAN"`` pass through), else
    infers ``"PBE+U"`` from a non-empty ``input.hubbards`` mapping, else
    ``"PBE"``.
    """
    run_type = task.get("run_type")
    if run_type:
        return {"GGA": "PBE", "GGA+U": "PBE+U"}.get(str(run_type), str(run_type))
    inp = task.get("input") or {}
    return "PBE+U" if inp.get("hubbards") else "PBE"


# ---------------------------------------------------------------------------
# Live fetchers — require mp-api
# ---------------------------------------------------------------------------

def _resolve_api_key(api_key: str | None, config: MPAdapterConfig) -> str:
    key = api_key or config.api_key or os.environ.get("MP_API_KEY")
    if not key:
        raise ValueError(
            "No Materials Project API key: pass api_key=, set "
            "MPAdapterConfig.api_key, or export MP_API_KEY."
        )
    return key


def _open_client(api_key: str | None, config: MPAdapterConfig) -> Any:
    try:
        from mp_api.client import MPRester
    except ImportError as exc:
        raise ImportError(
            "The Materials Project adapter needs mp-api; "
            "install it with: pip install qmatbridge[mp]"
        ) from exc
    return MPRester(_resolve_api_key(api_key, config), monitor=False)


def _to_plain(obj: Any) -> Any:
    """Convert mp-api / pymatgen objects to plain dicts where possible."""
    for attr in ("as_dict", "model_dump"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            return fn()
    return obj


def _summary_doc(mpr: Any, material_id: str, max_sites: int | None) -> dict[str, Any]:
    docs = mpr.materials.summary.search(
        material_ids=[material_id], fields=["material_id", "structure", "symmetry"]
    )
    if not docs:
        raise LookupError(f"Materials Project has no record for {material_id!r}")
    d = docs[0]
    out = {
        "structure": _to_plain(d.structure),
        "symmetry": _to_plain(d.symmetry) if d.symmetry is not None else {},
    }
    if max_sites is not None and len(out["structure"]["sites"]) > max_sites:
        raise ValueError(
            f"{material_id} has more than max_sites={max_sites} sites"
        )
    return out


def fetch_structure_metadata_from_mp(
    material_id: str,
    api_key: str | None = None,
    config: MPAdapterConfig | None = None,
) -> StructureMetadata:
    """Fetch crystal structure from the Materials Project API.

    Args:
        material_id: MP identifier, e.g. ``"mp-149"``.
        api_key:     MP API key.  Falls back to ``MPAdapterConfig.api_key``
                     then the ``MP_API_KEY`` environment variable.
        config:      Adapter configuration (honours ``max_sites``).

    Raises:
        ImportError: ``mp-api`` is not installed.
        ValueError:  No API key, disordered structure, or ``max_sites`` exceeded.
        LookupError: Unknown material ID.
    """
    cfg = config or MPAdapterConfig()
    with _open_client(api_key, cfg) as mpr:
        return structure_from_mp_doc(_summary_doc(mpr, material_id, cfg.max_sites))


_CALC_SUFFIXES = (
    "static",
    "structure optimization",
    "nscf",
    "deformation",
    "unrecognized",
)


def _run_type_of(calc_type: str) -> str:
    """``"GGA+U Static"`` -> ``"gga+u"`` (functional part, lower-case)."""
    low = str(calc_type).lower()
    cut = min((low.find(x) for x in _CALC_SUFFIXES if x in low), default=len(low))
    return low[:cut].strip()


def _pick_static_task(
    mpr: Any, material_id: str, run_types: tuple[str, ...] = ("GGA", "GGA+U")
) -> dict[str, Any]:
    """Return the task document of the material's static calculation.

    Only static tasks whose run type is in ``run_types`` are considered,
    taking the first run type (in preference order) that has any; ties are
    broken by sorted task ID so the choice is deterministic.  All matching
    task IDs are recorded under ``_candidates``.

    Raises:
        LookupError: If no static task has an acceptable run type.
    """
    mdocs = mpr.materials.search(
        material_ids=[material_id], fields=["material_id", "calc_types"]
    )
    if not mdocs:
        raise LookupError(f"Materials Project has no record for {material_id!r}")
    calc_types: Mapping[str, str] = mdocs[0].calc_types or {}
    static = {
        t: _run_type_of(c)
        for t, c in calc_types.items()
        if "static" in str(c).lower()
    }
    candidates: list[str] = []
    for rt in run_types:
        candidates = sorted(t for t, r in static.items() if r == rt.lower())
        if candidates:
            break
    if not candidates:
        have = sorted(set(static.values())) or ["none"]
        raise LookupError(
            f"No static calculation for {material_id!r} with run type in "
            f"{list(run_types)}; available static run types: {have}. "
            "Pass MPAdapterConfig(run_types=...) to choose another."
        )
    tasks = mpr.materials.tasks.search(task_ids=[candidates[-1]])
    if not tasks:
        raise LookupError(f"Task {candidates[-1]!r} not found")
    task = dict(_to_plain(tasks[0]))
    task.setdefault("task_id", candidates[-1])
    task["_candidates"] = candidates
    return task


def fetch_hamiltonian_metadata_from_mp(
    material_id: str,
    api_key: str | None = None,
    config: MPAdapterConfig | None = None,
) -> HamiltonianMetadata:
    """Fetch DFT Hamiltonian parameters from the Materials Project API.

    Selects the material's static VASP task, reads the plane-wave cutoff,
    electron count and spin setting from its inputs, and computes the
    plane-wave count from the fetched cell.

    Raises:
        ImportError, ValueError, LookupError: as for
            :func:`fetch_structure_metadata_from_mp`; also ``ValueError`` if
            the task lacks ``ENCUT`` or ``NELECT``.
    """
    cfg = config or MPAdapterConfig()
    with _open_client(api_key, cfg) as mpr:
        structure = structure_from_mp_doc(
            _summary_doc(mpr, material_id, cfg.max_sites)
        )
        task = _pick_static_task(mpr, material_id, cfg.run_types)
    return hamiltonian_from_mp_task_doc(task, structure)


def fetch_entry_from_mp(
    material_id: str,
    api_key: str | None = None,
    config: MPAdapterConfig | None = None,
    *,
    tags: list[str] | None = None,
) -> QMatEntry:
    """Fetch structure and Hamiltonian from MP and assemble a ``QMatEntry``.

    Provenance records the retrieval time (UTC) and the MP task used.
    """
    cfg = config or MPAdapterConfig()
    with _open_client(api_key, cfg) as mpr:
        structure = structure_from_mp_doc(_summary_doc(mpr, material_id, cfg.max_sites))
        task = _pick_static_task(mpr, material_id, cfg.run_types)
    hamiltonian = hamiltonian_from_mp_task_doc(task, structure)
    ref = build_material_reference_from_mp(
        material_id,
        functional=functional_from_mp_task_doc(task),
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        config=cfg,
    )
    ref.structure = structure
    ref.provenance.metadata["task_id"] = task.get("task_id")
    ref.provenance.metadata["candidate_task_ids"] = task.get("_candidates", [])
    return QMatEntry(reference=ref, hamiltonian=hamiltonian, tags=list(tags or []))
