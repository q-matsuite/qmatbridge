"""Cross-database deduplication of :class:`~qmatbridge.schema.QMatEntry` records.

The same crystal is often stored in several databases (Materials Project,
Alexandria, OQMD, ...), usually relaxed with slightly different settings and
often in a different cell.  Two kinds of evidence say that entries describe the
same material:

``shared_identifier``
    The entries share an external identifier, e.g. the same ICSD number, in
    ``provenance.primary`` or ``provenance.additional_ids``.

``geometry``
    The atomic environments agree.  The comparison does not depend on the choice
    of cell (primitive or conventional), the origin, the orientation, or the
    atom order, and it allows a relative tolerance on interatomic distances so
    that a PBE and a PBEsol relaxation of one structure still match.

Both are about the *material*, not the *calculation*: two entries of one
material with different functionals are duplicates here, and keep different
:meth:`~qmatbridge.schema.QMatEntry.canonical_hash` values.

The geometry test is a fingerprint comparison, not a symmetry analysis.  It
separates distinct phases of one composition (for example rocksalt and
zincblende) but is not a substitute for a full structure matcher on
borderline cases; the tolerance is yours to set.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from qmatbridge.basis import _lattice_vectors
from qmatbridge.schema import QMatEntry

__all__ = [
    "DuplicateGroup",
    "DuplicateLink",
    "deduplicate",
    "external_identifiers",
    "find_duplicates",
    "structures_match",
]

_Vec = tuple[float, float, float]
# (center element, neighbor element) -> nearest distances, ascending
_Environment = tuple[str, dict[str, list[float]]]

_SOURCE_ALIASES = {"mp": "materials_project"}


def external_identifiers(entry: QMatEntry) -> set[tuple[str, str]]:
    """Normalised ``(source, identifier)`` pairs that name *entry*'s material.

    Covers the primary identifier and ``additional_ids``.  Sources are
    lower-cased, and an OPTIMADE entry (source ``optimade:<provider>``,
    identifier ``<provider>:<id>``) is also listed under the provider's own
    name, so the same Materials Project record matches whether it came through
    the Materials Project adapter or through OPTIMADE.
    """
    prov = entry.reference.provenance
    out: set[tuple[str, str]] = set()
    for ident in [prov.primary, *prov.additional_ids]:
        source, value = ident.source.strip().lower(), ident.identifier.strip()
        if not source or not value:
            continue
        out.add((source, value))
        if source.startswith("optimade:") and value.lower().startswith(
            source.split(":", 1)[1] + ":"
        ):
            provider = source.split(":", 1)[1]
            out.add((_SOURCE_ALIASES.get(provider, provider), value.split(":", 1)[1]))
    return out


# ---------------------------------------------------------------------------
# Geometry fingerprint
# ---------------------------------------------------------------------------


def _cross(u: _Vec, v: _Vec) -> _Vec:
    return (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )


def _dot(u: _Vec, v: _Vec) -> float:
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def _environments(entry: QMatEntry, per_pair: int) -> list[_Environment]:
    """Per-atom list of the nearest *per_pair* distances to each neighbor element.

    The search radius grows until every element present has *per_pair*
    neighbors around every atom, so the result does not depend on the cell.
    """
    struct = entry.reference.structure
    a1, a2, a3 = _lattice_vectors(struct.lattice)
    vol = abs(_dot(a1, _cross(a2, a3)))
    if vol < 1e-9:
        raise ValueError("degenerate lattice")
    # perpendicular spacing of each family of lattice planes
    heights = [
        vol / math.sqrt(_dot(c, c))
        for c in (_cross(a2, a3), _cross(a3, a1), _cross(a1, a2))
    ]
    cart = [
        tuple(
            sum(f * a[k] for f, a in zip(site.frac_coords, (a1, a2, a3)))
            for k in range(3)
        )
        for site in struct.sites
    ]
    elements = sorted({s.element for s in struct.sites})
    radius = 1.6 * (vol / len(struct.sites)) ** (1 / 3) * per_pair ** (1 / 3)

    for _ in range(8):
        reach = [math.ceil(radius / h) + 1 for h in heights]
        shifts = [
            tuple(i * a1[k] + j * a2[k] + m * a3[k] for k in range(3))
            for i, j, m in itertools.product(*(range(-r, r + 1) for r in reach))
        ]
        envs: list[_Environment] = []
        complete = True
        for ci, site in enumerate(struct.sites):
            near: dict[str, list[float]] = {el: [] for el in elements}
            for nj, other in enumerate(struct.sites):
                for s in shifts:
                    d = math.dist(cart[ci], tuple(cart[nj][k] + s[k] for k in range(3)))
                    if 1e-6 < d <= radius:
                        near[other.element].append(d)
            for el in elements:
                near[el].sort()
                del near[el][per_pair:]
                if len(near[el]) < per_pair:
                    complete = False
            envs.append((site.element, near))
        if complete:
            return envs
        radius *= 1.5
    raise ValueError("could not collect enough neighbors to fingerprint the structure")


def _close(x: list[float], y: list[float], rtol: float) -> bool:
    return len(x) == len(y) and all(
        abs(p - q) <= rtol * max(p, q) for p, q in zip(x, y)
    )


def _same_env(a: _Environment, b: _Environment, rtol: float) -> bool:
    return (
        a[0] == b[0]
        and a[1].keys() == b[1].keys()
        and all(_close(a[1][el], b[1][el], rtol) for el in a[1])
    )


def _unique(envs: list[_Environment], rtol: float) -> list[_Environment]:
    kept: list[_Environment] = []
    for env in envs:
        if not any(_same_env(env, k, rtol) for k in kept):
            kept.append(env)
    return kept


def _covers(ea: list[_Environment], eb: list[_Environment], rtol: float) -> bool:
    """Every environment in *ea* occurs in *eb* and vice versa."""
    return all(any(_same_env(x, y, rtol) for y in eb) for x in ea) and all(
        any(_same_env(y, x, rtol) for x in ea) for y in eb
    )


def structures_match(
    a: QMatEntry, b: QMatEntry, *, rtol: float = 0.03, neighbors: int = 6
) -> bool:
    """Whether two entries have the same crystal structure within *rtol*.

    Both entries need atomic positions; without them the question has no answer
    and ``ValueError`` is raised.  The reduced formulas must be equal.  Every
    distinct atomic environment of one structure must appear in the other and
    vice versa, where an environment is the element of the atom plus, for each
    element, its nearest *neighbors* distances, compared with relative tolerance
    *rtol*.

    Args:
        rtol:      Relative tolerance on interatomic distances.  The default
                   (3 %) covers the lattice-constant spread between common
                   functionals; tighten it to separate near-identical phases.
        neighbors: Nearest distances kept per element pair.

    Raises:
        ValueError: If either entry has no ``structure.sites``.
    """
    sa, sb = a.reference.structure, b.reference.structure
    if not sa.sites or not sb.sites:
        raise ValueError("structures_match needs atomic positions on both entries")
    if sa.formula_reduced != sb.formula_reduced:
        return False
    return _covers(
        _unique(_environments(a, neighbors), rtol),
        _unique(_environments(b, neighbors), rtol),
        rtol,
    )


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


@dataclass
class DuplicateLink:
    """Evidence that entries *i* and *j* (indices into the input) are one material."""

    i: int
    j: int
    kind: str  # "shared_identifier" | "geometry"
    shared: list[tuple[str, str]] = field(default_factory=list)
    geometry_agrees: bool | None = None  # for identifier links: None = not checkable


@dataclass
class DuplicateGroup:
    """Entries judged to be the same material.

    ``indices`` are positions in the input list, ascending; ``links`` is the
    evidence, so a group joined only by a chain of matches shows which pairs
    were actually compared.
    """

    indices: list[int]
    links: list[DuplicateLink] = field(default_factory=list)

    @property
    def conflicts(self) -> list[DuplicateLink]:
        """Identifier links whose geometries disagree: worth a manual look."""
        return [
            link
            for link in self.links
            if link.kind == "shared_identifier" and link.geometry_agrees is False
        ]


def find_duplicates(
    entries: list[QMatEntry],
    *,
    use_identifiers: bool = True,
    use_geometry: bool = True,
    rtol: float = 0.03,
    neighbors: int = 6,
) -> list[DuplicateGroup]:
    """Group *entries* that describe the same material.

    Only groups with two or more members are returned, ordered by first index.
    Matches are transitive: if A matches B and B matches C, all three are one
    group.  Geometry is only compared between entries that have atomic
    positions and the same reduced formula, and pairs already joined by an
    identifier are not compared again except to record whether the geometries
    agree.

    Args:
        use_identifiers: Link entries that share an external identifier.
        use_geometry:    Link entries whose structures match; see
                         :func:`structures_match`.
        rtol, neighbors: Passed to :func:`structures_match`.
    """
    n = len(entries)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    links: list[DuplicateLink] = []
    ids = [external_identifiers(e) for e in entries] if use_identifiers else []
    envs: dict[int, list[_Environment]] = {}

    def has_sites(k: int) -> bool:
        return bool(entries[k].reference.structure.sites)

    def match(i: int, j: int) -> bool:
        if entries[i].reference.structure.formula_reduced != (
            entries[j].reference.structure.formula_reduced
        ):
            return False
        for k in (i, j):
            if k not in envs:
                envs[k] = _unique(_environments(entries[k], neighbors), rtol)
        return _covers(envs[i], envs[j], rtol)

    for i in range(n):
        for j in range(i + 1, n):
            shared = sorted(ids[i] & ids[j]) if use_identifiers else []
            if shared:
                agrees = match(i, j) if has_sites(i) and has_sites(j) else None
                links.append(DuplicateLink(i, j, "shared_identifier", shared, agrees))
                parent[find(i)] = find(j)
            elif use_geometry and has_sites(i) and has_sites(j) and match(i, j):
                links.append(DuplicateLink(i, j, "geometry"))
                parent[find(i)] = find(j)

    members: dict[int, list[int]] = {}
    for k in range(n):
        members.setdefault(find(k), []).append(k)
    groups = [
        DuplicateGroup(
            indices=idx,
            links=[lk for lk in links if find(lk.i) == root],
        )
        for root, idx in members.items()
        if len(idx) > 1
    ]
    return sorted(groups, key=lambda g: g.indices[0])


def deduplicate(
    entries: list[QMatEntry],
    *,
    prefer: Callable[[QMatEntry], Any] | None = None,
    use_identifiers: bool = True,
    use_geometry: bool = True,
    rtol: float = 0.03,
    neighbors: int = 6,
) -> list[QMatEntry]:
    """One entry per material, in input order of the kept entries.

    From each duplicate group the first entry is kept, or the one with the
    smallest ``prefer(entry)`` if a key function is given, e.g. to favour a
    source or a functional::

        deduplicate(
            entries,
            prefer=lambda e: e.reference.provenance.functional != "PBE",
        )

    The others are dropped; use :func:`find_duplicates` to see what was merged.
    The other options are those of :func:`find_duplicates`.
    """
    groups = find_duplicates(
        entries,
        use_identifiers=use_identifiers,
        use_geometry=use_geometry,
        rtol=rtol,
        neighbors=neighbors,
    )
    drop: set[int] = set()
    for g in groups:
        keep = (
            g.indices[0]
            if prefer is None
            else min(g.indices, key=lambda k: prefer(entries[k]))
        )
        drop.update(set(g.indices) - {keep})
    return [e for k, e in enumerate(entries) if k not in drop]
