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

import enum
import math
import os
import sys
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from qmatbridge.basis import cell_volume, num_plane_waves_from_ecut
from qmatbridge.schema import (
    BasisMetadata,
    ExternalIdentifier,
    HamiltonianMetadata,
    LatticeMetadata,
    MaterialReference,
    QMatEntry,
    SiteMetadata,
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
    "MaterialsProjectAdapter",
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


def _mapping(obj: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(obj, Mapping):
        raise ValueError(f"{where} must be an object, got {type(obj).__name__}")
    return obj


def _number(value: Any, where: str) -> float:
    """A finite float from a number or numeric string; ``ValueError`` otherwise."""
    if isinstance(value, bool):
        raise ValueError(f"{where} must be a number, got {value!r}")
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{where} must be a number, got {value!r}") from exc
    if not math.isfinite(x):
        raise ValueError(f"{where} must be finite, got {value!r}")
    return x


def _text(value: Any, where: str) -> str:
    """A string (or the value of a string-like Enum); ``ValueError`` otherwise."""
    if isinstance(value, enum.Enum):
        value = value.value
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where} must be a non-empty string, got {value!r}")
    return value


def structure_from_mp_doc(doc: Mapping[str, Any]) -> StructureMetadata:
    """Convert an MP summary document (as a dict) to ``StructureMetadata``.

    Expects ``structure`` in pymatgen ``Structure.as_dict()`` form
    (``lattice`` with ``a, b, c, alpha, beta, gamma``; ``sites`` each with a
    ``species`` list) and, optionally, ``symmetry`` with ``number``,
    ``symbol`` and ``crystal_system``.  Disordered sites are rejected.

    Fractional coordinates (``abc`` on each site) are recorded as
    ``StructureMetadata.sites`` when present on every site, so the entry's
    ``canonical_hash()`` covers the geometry; documents without them still
    convert, with ``sites`` empty.

    Every malformed input raises ``ValueError``: wrong shapes or types, missing
    keys, non-finite or non-positive lattice parameters, and invalid cells.

    Raises:
        ValueError: If the document is malformed, or a site is disordered.
    """
    doc_m = _mapping(doc, "MP document")
    try:
        struct = _mapping(doc_m["structure"], "structure")
        lat = _mapping(struct["lattice"], "structure.lattice")
        sites = struct["sites"]
    except KeyError as exc:
        raise ValueError(f"MP document is missing required key: {exc}") from exc

    params: list[float] = []
    for key in ("a", "b", "c", "alpha", "beta", "gamma"):
        if key not in lat:
            raise ValueError(f"MP document is missing required key: {key!r}")
        params.append(_number(lat[key], f"structure.lattice.{key}"))
    lattice = LatticeMetadata(
        a=params[0], b=params[1], c=params[2],
        alpha=params[3], beta=params[4], gamma=params[5],
    )
    cell_volume(lattice)  # rejects non-positive lengths and impossible angles

    if not isinstance(sites, (list, tuple)):
        raise ValueError(f"structure.sites must be a list, got {type(sites).__name__}")
    species: list[str] = []
    positions: list[tuple[float, float, float]] = []
    for i, site in enumerate(sites):
        where = f"structure.sites[{i}]"
        site_m = _mapping(site, where)
        occ = site_m.get("species")
        if not isinstance(occ, (list, tuple)) or not occ:
            raise ValueError(f"{where}.species must be a non-empty list")
        first = _mapping(occ[0], f"{where}.species[0]")
        if len(occ) != 1 or _number(first.get("occu", 1.0), f"{where}.occu") != 1.0:
            raise ValueError("disordered / partially occupied sites are not supported")
        species.append(_text(first.get("element"), f"{where}.species[0].element"))
        abc = site_m.get("abc")
        if abc is not None:
            if not isinstance(abc, (list, tuple)) or len(abc) != 3:
                raise ValueError(f"{where}.abc must be three fractional coordinates")
            x, y, z = (_number(c, f"{where}.abc[{k}]") for k, c in enumerate(abc))
            positions.append((x, y, z))
    if not species:
        raise ValueError("MP structure has no sites")
    if positions and len(positions) != len(species):
        raise ValueError(
            "structure.sites: fractional coordinates (abc) are present for only "
            f"{len(positions)} of {len(species)} sites"
        )

    sym_raw = doc_m.get("symmetry")
    sym = {} if sym_raw is None else _mapping(sym_raw, "symmetry")
    number = sym.get("number")
    if number is not None and (
        isinstance(number, bool)
        or not isinstance(number, int)
        or not 1 <= number <= 230
    ):
        raise ValueError(f"symmetry.number must be an integer 1-230, got {number!r}")
    symbol = sym.get("symbol")
    system = sym.get("crystal_system")
    lattice.spacegroup_number = number
    lattice.spacegroup_symbol = (
        None if symbol is None else _text(symbol, "symmetry.symbol")
    )
    lattice.crystal_system = (
        None if system is None else _text(system, "symmetry.crystal_system").lower()
    )

    counts = Counter(species)
    return StructureMetadata(
        formula_reduced=_hill_formula(_reduced_counts(counts)),
        formula_unit_cell=_hill_formula(counts),
        num_sites=len(species),
        species=species,
        lattice=lattice,
        is_periodic=True,
        sites=[SiteMetadata(el, pos) for el, pos in zip(species, positions)],
    )


def hamiltonian_from_mp_task_doc(
    task: Mapping[str, Any], structure: StructureMetadata
) -> HamiltonianMetadata:
    """Convert an MP VASP task document (as a dict) to ``HamiltonianMetadata``.

    Reads ``input.incar.ENCUT`` (eV), ``input.incar.ISPIN`` and
    ``input.parameters.NELECT``.  The plane-wave count is computed from the
    cutoff and ``structure.lattice`` via
    :func:`qmatbridge.basis.num_plane_waves_from_ecut`.

    Every malformed input raises ``ValueError``: wrong shapes or types, a
    missing or non-finite ``ENCUT``/``NELECT``, non-positive values, a
    non-integer electron count, ``ISPIN`` other than 1 or 2, or a cell and
    cutoff too large for exact plane-wave enumeration.

    Raises:
        ValueError: If the task document is malformed or unusable.
    """
    task_m = _mapping(task, "task document")
    inp = _mapping(task_m.get("input") or {}, "input")
    incar = _mapping(inp.get("incar") or {}, "input.incar")
    params = _mapping(inp.get("parameters") or {}, "input.parameters")
    if "ENCUT" not in incar:
        raise ValueError("task document has no input.incar.ENCUT")
    if "NELECT" not in params:
        raise ValueError("task document has no input.parameters.NELECT")

    ecut = _number(incar["ENCUT"], "input.incar.ENCUT")
    if ecut <= 0:
        raise ValueError(f"input.incar.ENCUT must be positive, got {ecut}")
    nelect = _number(params["NELECT"], "input.parameters.NELECT")
    if nelect != int(nelect):
        raise ValueError(f"non-integer NELECT ({nelect}) is not supported")
    if nelect <= 0:
        raise ValueError(f"input.parameters.NELECT must be positive, got {nelect}")
    ispin = _number(incar.get("ISPIN", 1), "input.incar.ISPIN")
    if ispin not in (1.0, 2.0):
        raise ValueError(f"input.incar.ISPIN must be 1 or 2, got {ispin}")

    basis = BasisMetadata(
        type="plane_wave",
        cutoff_energy_ev=ecut,
        num_plane_waves=num_plane_waves_from_ecut(structure.lattice, ecut),
    )
    return HamiltonianMetadata(
        num_electrons=int(nelect),
        spin_polarized=ispin == 2.0,
        basis=basis,
        metadata={"source_task_id": task_m.get("task_id")},
        valence_charges=valence_charges_from_mp_task_doc(task_m),
    )


def valence_charges_from_mp_task_doc(task: Mapping[str, Any]) -> dict[str, float]:
    """Per-element valence charges from a VASP task's POTCAR specification.

    Pairs ``input.potcar_spec[*].titel`` (e.g. ``"PAW_PBE Li_sv 23Jan2001"``)
    with ``input.parameters.ZVAL``, which VASP lists in POTCAR order.  Returns
    an empty dict, never an error, when either is absent, the lengths differ,
    a title cannot be parsed, or one element appears with two different
    charges: a missing charge is better than a guessed one.
    """
    inp = task.get("input")
    if not isinstance(inp, Mapping):
        return {}
    spec, params = inp.get("potcar_spec"), inp.get("parameters")
    zval = params.get("ZVAL") if isinstance(params, Mapping) else None
    if not (isinstance(spec, list) and isinstance(zval, list)):
        return {}
    if len(spec) != len(zval):
        return {}
    charges: dict[str, float] = {}
    for item, z in zip(spec, zval):
        titel = item.get("titel") if isinstance(item, Mapping) else None
        if not isinstance(titel, str) or isinstance(z, bool):
            return {}
        if not isinstance(z, (int, float)):
            return {}
        words = titel.split()
        if len(words) < 2 or not math.isfinite(z) or z <= 0:
            return {}
        element = words[1].split("_")[0]
        if not element.isalpha() or charges.setdefault(element, float(z)) != float(z):
            return {}
    return charges


def functional_from_mp_task_doc(task: Mapping[str, Any]) -> str:
    """Name the XC functional of an MP task document (e.g. ``"PBE+U"``).

    Uses ``run_type`` when present (``"GGA"`` → ``"PBE"``, ``"GGA+U"`` →
    ``"PBE+U"``; other run types such as ``"r2SCAN"`` pass through), else
    infers ``"PBE+U"`` from a non-empty ``input.hubbards`` mapping, else
    ``"PBE"``.
    """
    task_m = _mapping(task, "task document")
    run_type = task_m.get("run_type")
    if run_type:
        return {"GGA": "PBE", "GGA+U": "PBE+U"}.get(str(run_type), str(run_type))
    inp = task_m.get("input")
    hubbards = inp.get("hubbards") if isinstance(inp, Mapping) else None
    return "PBE+U" if hubbards else "PBE"


# ---------------------------------------------------------------------------
# Live fetchers — require mp-api
# ---------------------------------------------------------------------------

def _resolve_api_key(api_key: str | None, config: MPAdapterConfig) -> str:
    key = api_key or config.api_key or os.environ.get("MP_API_KEY")
    if not key:
        raise ValueError(
            "No Materials Project API key: pass api_key=, set "
            "MPAdapterConfig.api_key, or export MP_API_KEY.  QMatBridge ships no "
            "keys; get your own (free) at https://next-gen.materialsproject.org/api"
        )
    return key


def _open_client(api_key: str | None, config: MPAdapterConfig) -> Any:
    try:
        from mp_api.client import MPRester
    except ImportError as exc:
        hint = ""
        if sys.version_info < (3, 11):
            hint = (
                " Current mp-api / emmet-core releases do not import on Python "
                f"{sys.version_info.major}.{sys.version_info.minor}; "
                "use Python 3.11 or newer."
            )
        raise ImportError(
            'The Materials Project adapter needs mp-api and pymatgen: pip install '
            '"qmatbridge[mp]" (from a source checkout: pip install -e ".[mp]"). '
            f"Importing mp-api failed: {type(exc).__name__}: {exc}.{hint}"
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
    if not isinstance(out["structure"], Mapping):
        raise ValueError(f"Materials Project returned no structure for {material_id!r}")
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
    if hamiltonian.valence_charges:
        try:
            QMatEntry(ref, hamiltonian).check_electron_count()
        except (KeyError, ValueError):
            hamiltonian.valence_charges = {}  # inconsistent with NELECT: keep none
    ref.provenance.metadata["task_id"] = task.get("task_id")
    ref.provenance.metadata["candidate_task_ids"] = task.get("_candidates", [])
    return QMatEntry(reference=ref, hamiltonian=hamiltonian, tags=list(tags or []))


class MaterialsProjectAdapter:
    """The Materials Project adapter as a registry plugin.

    Satisfies :class:`qmatbridge.registry.Adapter`::

        from qmatbridge.registry import get_adapter

        adapter = get_adapter("materials_project")
        entry = adapter.fetch_entry("mp-149", tags=["silicon"])

    Args:
        config:  Adapter configuration (run types, ``max_sites``, ...).
        api_key: MP API key; falls back to ``config.api_key`` then ``MP_API_KEY``.
    """

    name = "materials_project"

    def __init__(
        self, config: MPAdapterConfig | None = None, *, api_key: str | None = None
    ) -> None:
        self._config = config
        self._api_key = api_key

    def fetch_entry(self, identifier: str, **options: Any) -> QMatEntry:
        """Fetch *identifier* (e.g. ``"mp-149"``); accepts ``tags=[...]``."""
        tags = options.pop("tags", None)
        if options:
            unexpected = ", ".join(sorted(options))
            raise TypeError(f"unexpected option(s) for materials_project: {unexpected}")
        return fetch_entry_from_mp(
            identifier, api_key=self._api_key, config=self._config, tags=tags
        )
