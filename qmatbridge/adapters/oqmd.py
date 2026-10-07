"""OQMD (Open Quantum Materials Database) adapter for QMatBridge.

Bridges the Open Quantum Materials Database (https://oqmd.org) to the neutral
intermediate representation.  OQMD holds ~1 million DFT-relaxed inorganic
structures computed with VASP and PBE, and its REST API needs no key.

What OQMD does and does not tell us
-----------------------------------
The REST API returns the relaxed cell (``unit_cell``), the atomic ``sites``
(``"Si @ 0 0 0"``, fractional) and the spacegroup *symbol*.  It does **not**
return the calculation settings (cutoff, electron count, spin treatment), so
those come from the published OQMD protocol and are recorded as assumptions:

* ``ENCUT`` = 520 eV (:attr:`OQMDAdapterConfig.encut_ev`),
* spin-polarized (:attr:`OQMDAdapterConfig.spin_polarized`),
* valence charges from :attr:`OQMDAdapterConfig.valence_charges`, falling back
  to a small built-in table limited to elements that have a single standard
  PAW potential.  For any other element the caller must supply the charge;
  the adapter never guesses.

Every assumption is written to ``hamiltonian.metadata`` so a reader can see
which numbers were fetched and which were configured.  The spacegroup number
is left unset (the API gives only the symbol), which keeps it out of the
canonical hash's spacegroup field.

No third-party dependency is needed: requests use :mod:`urllib` from the
standard library, with retries on transient server errors.

Offline use
-----------
``structure_from_oqmd_doc`` and ``hamiltonian_from_oqmd`` are pure converters;
:class:`OQMDAdapterConfig` accepts an ``http_get`` callable, so tests and
air-gapped runs can replay recorded responses.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from qmatbridge.adapters.materials_project import _hill_formula, _reduced_counts
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
    "OQMDAdapter",
    "OQMDAdapterConfig",
    "build_material_reference_from_oqmd",
    "fetch_entry_from_oqmd",
    "fetch_hamiltonian_metadata_from_oqmd",
    "fetch_structure_metadata_from_oqmd",
    "hamiltonian_from_oqmd",
    "structure_from_oqmd_doc",
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
        max_sites:  If set, refuse structures with more than this many sites.
        metadata:   Arbitrary extra config passed through to adapters.
        retries:    Extra attempts after a transient failure (HTTP 5xx, 429 or a
                    network error).
        backoff_s:  Delay before the first retry; doubles each time.
        encut_ev:   Plane-wave cutoff to record.  OQMD's published protocol uses
                    520 eV; the API does not return it.
        spin_polarized: Spin treatment to record (OQMD runs spin-polarized).
        valence_charges: Valence electrons per element, overriding the built-in
                    table.  Required for elements outside that table.
        http_get:   ``(url, timeout_s) -> bytes`` replacing the real HTTP call,
                    for recorded-response tests and offline use.
    """

    endpoint: str = _OQMD_REST_BASE
    timeout_s: float = 30.0
    max_sites: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    retries: int = 3
    backoff_s: float = 1.0
    encut_ev: float = 520.0
    spin_polarized: bool = True
    valence_charges: Mapping[str, float] = field(default_factory=dict)
    http_get: Callable[[str, float], bytes] | None = None


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
# Reference builder — no API call required
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
# Valence charges
# ---------------------------------------------------------------------------

#: Valence electrons for elements that have one standard PAW_PBE potential, so
#: the count does not depend on a pseudopotential choice.  Everything else
#: (alkali, alkaline-earth and transition metals, ...) has several variants and
#: must be given explicitly through ``OQMDAdapterConfig.valence_charges``.
_UNAMBIGUOUS_VALENCE: dict[str, float] = {
    "H": 1.0, "He": 2.0, "C": 4.0, "N": 5.0, "O": 6.0, "F": 7.0, "Ne": 8.0,
    "Si": 4.0, "P": 5.0, "S": 6.0, "Cl": 7.0, "Ar": 8.0,
}  # fmt: skip


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

_FIELDS = "name,entry_id,spacegroup,unit_cell,sites,natoms,calculation_label,band_gap"
_RETRY_STATUS = {429, 500, 502, 503, 504}


def _numeric_id(entry_id: str | int) -> int:
    raw = str(entry_id).strip().removeprefix("oqmd-")
    if not raw.isdigit():
        raise ValueError(f"not an OQMD entry id: {entry_id!r}")
    return int(raw)


def _default_get(url: str, timeout_s: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "qmatbridge"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        data: bytes = resp.read()
    return data


def _fetch_doc(entry_id: str | int, cfg: OQMDAdapterConfig) -> dict[str, Any]:
    """Fetch the OQMD record for *entry_id*, retrying transient failures."""
    n = _numeric_id(entry_id)
    query = urllib.parse.urlencode(
        {"fields": _FIELDS, "filter": f"entry_id={n}", "limit": 1}, safe=",="
    )
    url = f"{cfg.endpoint.rstrip('/')}/formationenergy?{query}"
    get = cfg.http_get or _default_get
    delay = cfg.backoff_s
    last: Exception | None = None
    for attempt in range(cfg.retries + 1):
        try:
            payload = json.loads(get(url, cfg.timeout_s))
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRY_STATUS:
                raise ValueError(f"OQMD returned HTTP {exc.code} for oqmd-{n}") from exc
            last = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
        except json.JSONDecodeError as exc:
            # OQMD answers with an HTML error page when it is overloaded.
            last = exc
        if attempt < cfg.retries:
            time.sleep(delay)
            delay *= 2
    else:
        raise ConnectionError(
            f"could not fetch oqmd-{n} from {cfg.endpoint} after "
            f"{cfg.retries + 1} attempt(s): {last}"
        ) from last
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data:
        raise ValueError(f"OQMD has no entry with id {n}")
    doc = data[0]
    if not isinstance(doc, dict):
        raise ValueError("OQMD returned an unexpected record shape")
    return doc


# ---------------------------------------------------------------------------
# Pure converters
# ---------------------------------------------------------------------------


def _finite(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{where}: expected a number, got {type(value).__name__}")
    try:
        x = float(value)
    except ValueError:
        raise ValueError(f"{where}: expected a number, got {value!r}") from None
    if not math.isfinite(x):
        raise ValueError(f"{where}: must be finite, got {value!r}")
    return x


def _lattice_from_vectors(cell: Any) -> tuple[float, float, float, float, float, float]:
    if not (isinstance(cell, (list, tuple)) and len(cell) == 3):
        raise ValueError("unit_cell must be three lattice vectors")
    vecs = []
    for i, v in enumerate(cell):
        if not (isinstance(v, (list, tuple)) and len(v) == 3):
            raise ValueError(f"unit_cell[{i}] must have three components")
        vecs.append([_finite(c, f"unit_cell[{i}][{k}]") for k, c in enumerate(v)])
    lengths = [math.sqrt(sum(c * c for c in v)) for v in vecs]
    if not all(n > 0 for n in lengths):
        raise ValueError("unit_cell has a zero-length lattice vector")

    def angle(i: int, j: int) -> float:
        dot = sum(p * q for p, q in zip(vecs[i], vecs[j]))
        cosine = dot / (lengths[i] * lengths[j])
        return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

    return (*lengths, angle(1, 2), angle(0, 2), angle(0, 1))  # type: ignore[return-value]


def _parse_site(text: Any, i: int) -> SiteMetadata:
    if not isinstance(text, str) or "@" not in text:
        raise ValueError(f"sites[{i}]: expected 'El @ x y z', got {text!r}")
    el, _, pos = text.partition("@")
    coords = pos.split()
    element = el.strip()
    if not element.isalpha() or len(coords) != 3:
        raise ValueError(f"sites[{i}]: expected 'El @ x y z', got {text!r}")
    x, y, z = (_finite(c, f"sites[{i}]") for c in coords)
    return SiteMetadata(element=element, frac_coords=(x, y, z))


def structure_from_oqmd_doc(doc: Mapping[str, Any]) -> StructureMetadata:
    """Convert one OQMD ``formationenergy`` record to ``StructureMetadata``.

    Lattice lengths and angles are derived from ``unit_cell`` (Cartesian
    vectors, Å).  The spacegroup symbol is kept; the number is not available
    from the API and stays ``None``.

    Raises:
        ValueError: If the record is malformed or has no sites.
    """
    if not isinstance(doc, Mapping):
        raise ValueError("OQMD record must be a mapping")
    for key in ("unit_cell", "sites"):
        if key not in doc:
            raise ValueError(f"OQMD record is missing required key: {key!r}")
    a, b, c, alpha, beta, gamma = _lattice_from_vectors(doc["unit_cell"])
    raw_sites = doc["sites"]
    if not isinstance(raw_sites, (list, tuple)) or not raw_sites:
        raise ValueError("OQMD record has no sites")
    sites = [_parse_site(t, i) for i, t in enumerate(raw_sites)]
    symbol = doc.get("spacegroup")
    lattice = LatticeMetadata(
        a=a, b=b, c=c, alpha=alpha, beta=beta, gamma=gamma,
        spacegroup_symbol=symbol if isinstance(symbol, str) and symbol else None,
    )  # fmt: skip
    lattice.volume_ang3 = cell_volume(lattice)  # also rejects impossible cells
    counts = Counter(s.element for s in sites)
    return StructureMetadata(
        formula_reduced=_hill_formula(_reduced_counts(counts)),
        formula_unit_cell=_hill_formula(counts),
        num_sites=len(sites),
        species=[s.element for s in sites],
        lattice=lattice,
        sites=sites,
    )


def hamiltonian_from_oqmd(
    structure: StructureMetadata, config: OQMDAdapterConfig | None = None
) -> HamiltonianMetadata:
    """Build ``HamiltonianMetadata`` for an OQMD structure from the OQMD protocol.

    Cutoff, spin treatment and valence charges are *configured*, not fetched;
    see the module docstring.  They are listed under ``metadata["assumed"]``.

    Raises:
        ValueError: If an element has no valence charge in the config or the
            built-in table.
    """
    cfg = config or OQMDAdapterConfig()
    charges: dict[str, float] = {}
    missing: list[str] = []
    for el in sorted(set(structure.species)):
        if el in cfg.valence_charges:
            charges[el] = float(cfg.valence_charges[el])
        elif el in _UNAMBIGUOUS_VALENCE:
            charges[el] = _UNAMBIGUOUS_VALENCE[el]
        else:
            missing.append(el)
    if missing:
        raise ValueError(
            "no valence charge for element(s) "
            f"{', '.join(missing)}: OQMD does not publish the electron count and "
            "these elements have several PAW potentials. Pass "
            "OQMDAdapterConfig(valence_charges={...}) with the number of valence "
            "electrons of the potential you intend."
        )
    total = sum(charges[el] for el in structure.species)
    if total != int(total) or total <= 0:
        raise ValueError(f"valence charges give a non-integer electron count ({total})")
    return HamiltonianMetadata(
        num_electrons=int(total),
        spin_polarized=cfg.spin_polarized,
        basis=BasisMetadata(
            type="plane_wave",
            cutoff_energy_ev=cfg.encut_ev,
            num_plane_waves=num_plane_waves_from_ecut(structure.lattice, cfg.encut_ev),
        ),
        metadata={"assumed": ["cutoff_energy_ev", "spin_polarized", "valence_charges"]},
        valence_charges=charges,
    )


# ---------------------------------------------------------------------------
# Live fetchers
# ---------------------------------------------------------------------------


def _checked_structure(
    doc: Mapping[str, Any], cfg: OQMDAdapterConfig
) -> StructureMetadata:
    structure = structure_from_oqmd_doc(doc)
    if cfg.max_sites is not None and structure.num_sites > cfg.max_sites:
        raise ValueError(
            f"structure has {structure.num_sites} sites, "
            f"more than max_sites={cfg.max_sites}"
        )
    return structure


def fetch_structure_metadata_from_oqmd(
    entry_id: str | int,
    config: OQMDAdapterConfig | None = None,
) -> StructureMetadata:
    """Fetch the crystal structure of an OQMD entry.

    Raises:
        ValueError: Unknown entry, malformed record, or more sites than
            ``config.max_sites``.
        ConnectionError: OQMD stayed unreachable through all retries.
    """
    cfg = config or OQMDAdapterConfig()
    return _checked_structure(_fetch_doc(entry_id, cfg), cfg)


def fetch_hamiltonian_metadata_from_oqmd(
    entry_id: str | int,
    config: OQMDAdapterConfig | None = None,
) -> HamiltonianMetadata:
    """Fetch an entry's structure and build its Hamiltonian metadata.

    See :func:`hamiltonian_from_oqmd` for what is assumed rather than fetched.
    """
    cfg = config or OQMDAdapterConfig()
    return hamiltonian_from_oqmd(fetch_structure_metadata_from_oqmd(entry_id, cfg), cfg)


def fetch_entry_from_oqmd(
    entry_id: str | int,
    config: OQMDAdapterConfig | None = None,
    *,
    tags: list[str] | None = None,
) -> QMatEntry:
    """Fetch an OQMD entry and assemble a ``QMatEntry`` (one request)."""
    cfg = config or OQMDAdapterConfig()
    doc = _fetch_doc(entry_id, cfg)
    structure = _checked_structure(doc, cfg)
    hamiltonian = hamiltonian_from_oqmd(structure, cfg)
    ref = build_material_reference_from_oqmd(
        entry_id,
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        config=cfg,
    )
    ref.structure = structure
    label = doc.get("calculation_label")
    if isinstance(label, str):
        ref.provenance.metadata["calculation_label"] = label
    entry = QMatEntry(reference=ref, hamiltonian=hamiltonian, tags=list(tags or []))
    entry.check_electron_count()
    return entry


class OQMDAdapter:
    """The OQMD adapter as a registry plugin.

    Satisfies :class:`qmatbridge.registry.Adapter`::

        from qmatbridge.registry import get_adapter

        entry = get_adapter("oqmd").fetch_entry("oqmd-1214579")
    """

    name = "oqmd"

    def __init__(self, config: OQMDAdapterConfig | None = None) -> None:
        self._config = config

    def fetch_entry(self, identifier: str, **options: Any) -> QMatEntry:
        """Fetch *identifier* (``"oqmd-1234"`` or ``1234``); accepts ``tags=[...]``."""
        tags = options.pop("tags", None)
        if options:
            unexpected = ", ".join(sorted(options))
            raise TypeError(f"unexpected option(s) for oqmd: {unexpected}")
        return fetch_entry_from_oqmd(identifier, self._config, tags=tags)
