"""Generic OPTIMADE adapter for QMatBridge.

`OPTIMADE <https://www.optimade.org>`_ is a common REST API implemented by many
materials databases (Alexandria, AFLOW, JARVIS, NOMAD, MC3D, OQMD, the
Materials Project, COD, ...).  One adapter therefore covers all of them: it
reads a ``structures`` entry and converts it to the neutral representation.

What OPTIMADE does and does not tell us
---------------------------------------
A ``structures`` entry carries the lattice vectors, the Cartesian site
positions and the species, so the structure is *fetched*.  It carries no
calculation settings, so the following are *configured* and listed under
``hamiltonian.metadata["assumed"]``:

* the plane-wave cutoff (:attr:`OptimadeAdapterConfig.encut_ev`, **required**:
  there is no sensible default across databases),
* the spin treatment (:attr:`OptimadeAdapterConfig.spin_polarized`),
* the valence charges (:attr:`OptimadeAdapterConfig.valence_charges`, with the
  same small built-in table of single-potential elements as the OQMD adapter).

Provenance fields (functional, pseudopotential, code) are likewise only
recorded when the caller supplies them; OPTIMADE does not define them.

Only ordered, fully periodic structures are accepted.  Disordered sites
(several ``chemical_symbols`` or ``concentration < 1``), vacancies and
structures that are not periodic in all three directions raise ``ValueError``
rather than being silently approximated.

No third-party dependency is needed: requests use :mod:`urllib` from the
standard library, with retries on transient server errors.

Offline use
-----------
``structure_from_optimade_doc`` is a pure converter, and
:class:`OptimadeAdapterConfig` accepts an ``http_get`` callable so tests and
air-gapped runs can replay recorded responses.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from qmatbridge.adapters.materials_project import _hill_formula, _reduced_counts
from qmatbridge.adapters.oqmd import (
    _RETRY_STATUS,
    _UNAMBIGUOUS_VALENCE,
    _default_get,
    _finite,
    _lattice_from_vectors,
)
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
    "KNOWN_PROVIDERS",
    "OptimadeAdapter",
    "OptimadeAdapterConfig",
    "fetch_entry_from_optimade",
    "fetch_hamiltonian_metadata_from_optimade",
    "fetch_structure_metadata_from_optimade",
    "hamiltonian_from_optimade",
    "structure_from_optimade_doc",
]

#: Provider shortcuts: name -> OPTIMADE base URL (without ``/v1``).  Only
#: endpoints that have been seen to answer are listed; any other OPTIMADE
#: server works through ``OptimadeAdapterConfig(base_url=...)``.  The registry
#: of providers is at https://providers.optimade.org.
KNOWN_PROVIDERS: dict[str, str] = {
    "alexandria-pbe": "https://alexandria.icams.rub.de/pbe",
    "alexandria-pbesol": "https://alexandria.icams.rub.de/pbesol",
    "mp": "https://optimade.materialsproject.org",
}


# ---------------------------------------------------------------------------
# Adapter configuration
# ---------------------------------------------------------------------------


@dataclass
class OptimadeAdapterConfig:
    """Configuration for the OPTIMADE adapter.

    Attributes:
        base_url:   OPTIMADE server root, e.g. ``"https://example.org/optimade"``
                    (the ``/v1`` path is added).  Optional when the identifier
                    carries a known provider prefix (``"mp:mp-149"``) or
                    ``provider`` is set.
        provider:   Name from :data:`KNOWN_PROVIDERS`, used when ``base_url`` is
                    not given.
        timeout_s:  HTTP request timeout in seconds.
        max_sites:  If set, refuse structures with more than this many sites.
        metadata:   Arbitrary extra config recorded in the provenance.
        retries:    Extra attempts after a transient failure (HTTP 5xx, 429 or a
                    network error).
        backoff_s:  Delay before the first retry; doubles each time.
        encut_ev:   Plane-wave cutoff to record.  Required to build a
                    Hamiltonian: OPTIMADE does not return it.
        spin_polarized: Spin treatment to record.
        valence_charges: Valence electrons per element, overriding the built-in
                    table.  Required for elements outside that table.
        functional, pseudopotential, code, code_version: Provenance to record,
                    if known.  Left unset otherwise.
        http_get:   ``(url, timeout_s) -> bytes`` replacing the real HTTP call,
                    for recorded-response tests and offline use.
    """

    base_url: str | None = None
    provider: str | None = None
    timeout_s: float = 30.0
    max_sites: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    retries: int = 3
    backoff_s: float = 1.0
    encut_ev: float | None = None
    spin_polarized: bool = False
    valence_charges: Mapping[str, float] = field(default_factory=dict)
    functional: str | None = None
    pseudopotential: str | None = None
    code: str | None = None
    code_version: str | None = None
    http_get: Callable[[str, float], bytes] | None = None


# ---------------------------------------------------------------------------
# Identifier and URL handling
# ---------------------------------------------------------------------------


def _resolve_target(
    identifier: str | int, cfg: OptimadeAdapterConfig
) -> tuple[str, str, str]:
    """Return ``(source_label, base_url, entry_id)`` for *identifier*.

    *identifier* is ``"<provider>:<id>"`` for a known provider, or a bare id
    with ``base_url`` / ``provider`` set in the config.
    """
    raw = str(identifier).strip()
    provider = cfg.provider
    if ":" in raw:
        prefix, _, rest = raw.partition(":")
        if prefix in KNOWN_PROVIDERS:
            provider, raw = prefix, rest
    if cfg.base_url:
        base = cfg.base_url
        label = provider or urllib.parse.urlsplit(base).netloc
    elif provider:
        if provider not in KNOWN_PROVIDERS:
            known = ", ".join(sorted(KNOWN_PROVIDERS))
            raise ValueError(f"unknown OPTIMADE provider {provider!r} (known: {known})")
        base, label = KNOWN_PROVIDERS[provider], provider
    else:
        raise ValueError(
            "no OPTIMADE server: use a '<provider>:<id>' identifier "
            f"({', '.join(sorted(KNOWN_PROVIDERS))}) or set "
            "OptimadeAdapterConfig(base_url=...)"
        )
    if not raw or any(ch in raw for ch in "/?# \t\n"):
        raise ValueError(f"not an OPTIMADE entry id: {identifier!r}")
    return label, base.rstrip("/"), raw


def _structure_url(base: str, entry_id: str) -> str:
    return f"{base}/v1/structures/{urllib.parse.quote(entry_id, safe='')}"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _fetch_doc(
    url: str, cfg: OptimadeAdapterConfig, entry_id: str
) -> dict[str, Any]:
    """GET *url* and return the ``data`` object, retrying transient failures."""
    get = cfg.http_get or _default_get
    delay = cfg.backoff_s
    last: Exception | None = None
    for attempt in range(cfg.retries + 1):
        try:
            payload = json.loads(get(url, cfg.timeout_s))
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ValueError(f"no OPTIMADE structure with id {entry_id!r}") from exc
            if exc.code not in _RETRY_STATUS:
                raise ValueError(
                    f"OPTIMADE server returned HTTP {exc.code} for {entry_id!r}"
                ) from exc
            last = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
        except json.JSONDecodeError as exc:
            # Overloaded servers answer with an HTML error page.
            last = exc
        if attempt < cfg.retries:
            time.sleep(delay)
            delay *= 2
    else:
        raise ConnectionError(
            f"could not fetch {entry_id!r} from {url} after "
            f"{cfg.retries + 1} attempt(s): {last}"
        ) from last
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(payload, dict) and payload.get("errors"):
        raise ValueError(f"OPTIMADE server reported errors for {entry_id!r}")
    if isinstance(data, list):  # a filter-style answer: exactly one entry expected
        data = data[0] if len(data) == 1 else None
    if not isinstance(data, dict):
        raise ValueError(f"no OPTIMADE structure with id {entry_id!r}")
    return data


# ---------------------------------------------------------------------------
# Pure converters
# ---------------------------------------------------------------------------


def _matrix3(value: Any, where: str) -> list[list[float]]:
    if not (isinstance(value, (list, tuple)) and len(value) == 3):
        raise ValueError(f"{where} must be three vectors")
    rows = []
    for i, v in enumerate(value):
        if not (isinstance(v, (list, tuple)) and len(v) == 3):
            raise ValueError(f"{where}[{i}] must have three components")
        if any(c is None for c in v):
            raise ValueError(f"{where}[{i}] has unknown (null) components")
        rows.append([_finite(c, f"{where}[{i}][{k}]") for k, c in enumerate(v)])
    return rows


def _det3(m: list[list[float]]) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def _fractional(
    lattice: list[list[float]], cart: list[float]
) -> tuple[float, float, float]:
    """Fractional coordinates of *cart* in the cell, wrapped into [0, 1) (Cramer)."""
    # Columns of the linear system are the lattice vectors.
    cols = [[lattice[j][i] for j in range(3)] for i in range(3)]
    det = _det3(cols)
    frac = []
    for k in range(3):
        m = [row[:] for row in cols]
        for i in range(3):
            m[i][k] = cart[i]
        x = _det3(m) / det
        frac.append(x - math.floor(x))
    return (frac[0], frac[1], frac[2])


def _check_ordered(attrs: Mapping[str, Any]) -> dict[str, str]:
    """Return ``species name -> element`` or raise for disorder / vacancies."""
    mapping: dict[str, str] = {}
    species = attrs.get("species")
    if not isinstance(species, (list, tuple)) or not species:
        raise ValueError("OPTIMADE record has no species")
    for sp in species:
        if not isinstance(sp, Mapping) or "name" not in sp:
            raise ValueError("OPTIMADE species entry is malformed")
        symbols = sp.get("chemical_symbols")
        conc = sp.get("concentration")
        if (
            not isinstance(symbols, (list, tuple))
            or len(symbols) != 1
            or symbols[0] in ("X", "vacancy")
            or not isinstance(conc, (list, tuple))
            or len(conc) != 1
            or not math.isclose(_finite(conc[0], "concentration"), 1.0, abs_tol=1e-9)
        ):
            raise ValueError(
                f"species {sp['name']!r} is disordered or a vacancy; only ordered "
                "structures are supported"
            )
        element = symbols[0]
        if not isinstance(element, str) or not element.isalpha():
            raise ValueError(
                f"species {sp['name']!r} has an invalid element {element!r}"
            )
        mapping[str(sp["name"])] = element
    return mapping


def structure_from_optimade_doc(doc: Mapping[str, Any]) -> StructureMetadata:
    """Convert one OPTIMADE ``structures`` entry to ``StructureMetadata``.

    Lattice lengths and angles come from ``lattice_vectors`` (Å) and the sites
    are converted from ``cartesian_site_positions`` to fractional coordinates
    wrapped into [0, 1).  The spacegroup is not read: it is optional in
    OPTIMADE and often ``null``.

    Raises:
        ValueError: If the record is malformed, not fully periodic, disordered,
            or has no sites.
    """
    if not isinstance(doc, Mapping):
        raise ValueError("OPTIMADE record must be a mapping")
    attrs = doc.get("attributes")
    if not isinstance(attrs, Mapping):
        raise ValueError("OPTIMADE record is missing 'attributes'")
    for key in ("lattice_vectors", "cartesian_site_positions", "species_at_sites"):
        if attrs.get(key) is None:
            raise ValueError(f"OPTIMADE record is missing required attribute {key!r}")
    dims = attrs.get("dimension_types")
    if dims is not None and list(dims) != [1, 1, 1]:
        raise ValueError(
            "structure is not periodic in all three directions "
            f"(dimension_types={dims})"
        )
    elements = _check_ordered(attrs)
    lattice_vectors = _matrix3(attrs["lattice_vectors"], "lattice_vectors")
    a, b, c, alpha, beta, gamma = _lattice_from_vectors(lattice_vectors)
    if abs(_det3(lattice_vectors)) < 1e-9:
        raise ValueError("lattice_vectors are linearly dependent")
    lattice = LatticeMetadata(a=a, b=b, c=c, alpha=alpha, beta=beta, gamma=gamma)
    lattice.volume_ang3 = cell_volume(lattice)  # also rejects impossible cells

    positions = attrs["cartesian_site_positions"]
    names = attrs["species_at_sites"]
    if (
        not isinstance(positions, (list, tuple))
        or not isinstance(names, (list, tuple))
        or not positions
        or len(positions) != len(names)
    ):
        raise ValueError("cartesian_site_positions and species_at_sites disagree")
    sites = []
    for i, (pos, name) in enumerate(zip(positions, names)):
        if name not in elements:
            raise ValueError(f"sites[{i}]: unknown species {name!r}")
        cart = _matrix3([pos, pos, pos], f"sites[{i}]")[0]
        sites.append(
            SiteMetadata(
                element=elements[name],
                frac_coords=_fractional(lattice_vectors, cart),
            )
        )
    counts = Counter(s.element for s in sites)
    return StructureMetadata(
        formula_reduced=_hill_formula(_reduced_counts(counts)),
        formula_unit_cell=_hill_formula(counts),
        num_sites=len(sites),
        species=[s.element for s in sites],
        lattice=lattice,
        sites=sites,
    )


def hamiltonian_from_optimade(
    structure: StructureMetadata, config: OptimadeAdapterConfig
) -> HamiltonianMetadata:
    """Build ``HamiltonianMetadata`` for an OPTIMADE structure from configuration.

    Cutoff, spin treatment and valence charges are *configured*, not fetched;
    see the module docstring.  They are listed under ``metadata["assumed"]``.

    Raises:
        ValueError: If ``config.encut_ev`` is unset, or an element has no
            valence charge in the config or the built-in table.
    """
    if config.encut_ev is None or not config.encut_ev > 0:
        raise ValueError(
            "OPTIMADE does not publish the plane-wave cutoff: pass "
            "OptimadeAdapterConfig(encut_ev=...) with the cutoff (eV) you intend"
        )
    charges: dict[str, float] = {}
    missing: list[str] = []
    for el in sorted(set(structure.species)):
        if el in config.valence_charges:
            charges[el] = float(config.valence_charges[el])
        elif el in _UNAMBIGUOUS_VALENCE:
            charges[el] = _UNAMBIGUOUS_VALENCE[el]
        else:
            missing.append(el)
    if missing:
        raise ValueError(
            "no valence charge for element(s) "
            f"{', '.join(missing)}: OPTIMADE does not publish the electron count and "
            "these elements have several PAW potentials. Pass "
            "OptimadeAdapterConfig(valence_charges={...}) with the number of valence "
            "electrons of the potential you intend."
        )
    total = sum(charges[el] for el in structure.species)
    if total != int(total) or total <= 0:
        raise ValueError(f"valence charges give a non-integer electron count ({total})")
    return HamiltonianMetadata(
        num_electrons=int(total),
        spin_polarized=config.spin_polarized,
        basis=BasisMetadata(
            type="plane_wave",
            cutoff_energy_ev=config.encut_ev,
            num_plane_waves=num_plane_waves_from_ecut(
                structure.lattice, config.encut_ev
            ),
        ),
        metadata={"assumed": ["cutoff_energy_ev", "spin_polarized", "valence_charges"]},
        valence_charges=charges,
    )


# ---------------------------------------------------------------------------
# Live fetchers
# ---------------------------------------------------------------------------


def _fetch_checked(
    identifier: str | int, cfg: OptimadeAdapterConfig
) -> tuple[str, str, str, StructureMetadata, dict[str, Any]]:
    label, base, entry_id = _resolve_target(identifier, cfg)
    doc = _fetch_doc(_structure_url(base, entry_id), cfg, entry_id)
    structure = structure_from_optimade_doc(doc)
    if cfg.max_sites is not None and structure.num_sites > cfg.max_sites:
        raise ValueError(
            f"structure has {structure.num_sites} sites, "
            f"more than max_sites={cfg.max_sites}"
        )
    return label, base, entry_id, structure, doc


def fetch_structure_metadata_from_optimade(
    identifier: str | int,
    config: OptimadeAdapterConfig | None = None,
) -> StructureMetadata:
    """Fetch the crystal structure of an OPTIMADE entry.

    Raises:
        ValueError: Unknown entry or server, malformed or unsupported (disordered,
            non-periodic) record, or more sites than ``config.max_sites``.
        ConnectionError: The server stayed unreachable through all retries.
    """
    return _fetch_checked(identifier, config or OptimadeAdapterConfig())[3]


def fetch_hamiltonian_metadata_from_optimade(
    identifier: str | int,
    config: OptimadeAdapterConfig,
) -> HamiltonianMetadata:
    """Fetch an entry's structure and build its Hamiltonian metadata.

    ``config.encut_ev`` is required; see :func:`hamiltonian_from_optimade`.
    """
    return hamiltonian_from_optimade(
        fetch_structure_metadata_from_optimade(identifier, config), config
    )


def fetch_entry_from_optimade(
    identifier: str | int,
    config: OptimadeAdapterConfig,
    *,
    tags: list[str] | None = None,
) -> QMatEntry:
    """Fetch an OPTIMADE entry and assemble a ``QMatEntry`` (one request)."""
    label, base, entry_id, structure, doc = _fetch_checked(identifier, config)
    hamiltonian = hamiltonian_from_optimade(structure, config)
    metadata: dict[str, Any] = {**config.metadata, "optimade_id": entry_id}
    attrs = doc.get("attributes", {})
    if isinstance(attrs, Mapping) and isinstance(attrs.get("last_modified"), str):
        metadata["last_modified"] = attrs["last_modified"]
    ref = MaterialReference(
        provenance=SourceProvenance(
            primary=ExternalIdentifier(
                source=f"optimade:{label}",
                identifier=f"{label}:{entry_id}",
                url=_structure_url(base, entry_id),
            ),
            functional=config.functional,
            pseudopotential=config.pseudopotential,
            code=config.code,
            code_version=config.code_version,
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            metadata=metadata,
        ),
        structure=structure,
    )
    entry = QMatEntry(reference=ref, hamiltonian=hamiltonian, tags=list(tags or []))
    entry.check_electron_count()
    return entry


class OptimadeAdapter:
    """The OPTIMADE adapter as a registry plugin.

    Satisfies :class:`qmatbridge.registry.Adapter`::

        from qmatbridge.adapters.optimade import OptimadeAdapter, OptimadeAdapterConfig
        from qmatbridge.registry import get_adapter

        adapter = get_adapter("optimade", config=OptimadeAdapterConfig(encut_ev=520.0))
        entry = adapter.fetch_entry("alexandria-pbe:agm000999956")
    """

    name = "optimade"

    def __init__(self, config: OptimadeAdapterConfig | None = None) -> None:
        self._config = config or OptimadeAdapterConfig()

    def fetch_entry(self, identifier: str, **options: Any) -> QMatEntry:
        """Fetch *identifier*: ``"<provider>:<id>"`` or a bare id plus ``base_url``."""
        tags = options.pop("tags", None)
        if options:
            unexpected = ", ".join(sorted(options))
            raise TypeError(f"unexpected option(s) for optimade: {unexpected}")
        return fetch_entry_from_optimade(identifier, self._config, tags=tags)
