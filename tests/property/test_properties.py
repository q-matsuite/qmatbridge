"""Property-based tests (Hypothesis): the reader, the hash, the converters, the counter.

These are the stress tests that found the 0.2.0 defects (see tests/unit/test_hardening.py
for the pinned regressions), kept so that they run on every change.
"""

from __future__ import annotations

import copy
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from qmatbridge.adapters.materials_project import (
    hamiltonian_from_mp_task_doc,
    structure_from_mp_doc,
)
from qmatbridge.basis import cell_volume, num_plane_waves_exact
from qmatbridge.io import (
    EntryFormatError,
    entry_from_dict,
    read_entry_json,
    to_dict,
    write_entry_json,
)
from qmatbridge.schema import (
    BasisMetadata,
    ExportMetadata,
    ExternalIdentifier,
    HamiltonianMetadata,
    LatticeMetadata,
    MaterialReference,
    OracleMetadata,
    QMatEntry,
    SiteMetadata,
    SourceProvenance,
    StructureMetadata,
)

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)

# ------------------------------------------------------------------ strategies

finite = st.floats(allow_nan=False, allow_infinity=False)
text = st.text(max_size=12)
json_scalar = (
    st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=20)
)
json_value = st.recursive(
    json_scalar,
    lambda c: st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=8), c, max_size=4),
    max_leaves=12,
)
metadata = st.dictionaries(
    st.text(max_size=6),
    st.recursive(
        st.none() | st.booleans() | st.integers(-(10**12), 10**12) | finite | text,
        lambda c: st.lists(c, max_size=3) | st.dictionaries(st.text(max_size=4), c, max_size=3),
        max_leaves=6,
    ),
    max_size=3,
)


sites = st.builds(
    SiteMetadata,
    element=st.sampled_from(["H", "Li", "O", "Si", "Fe"]),
    frac_coords=st.tuples(finite, finite, finite),
    metadata=st.just({}),
)
# coordinates on a 1e-3 grid: far from any 6-decimal rounding boundary
grid_sites = st.builds(
    SiteMetadata,
    element=st.sampled_from(["H", "Li", "O", "Si", "Fe"]),
    frac_coords=st.tuples(*[st.integers(0, 999).map(lambda n: n / 1000)] * 3),
)


@st.composite
def entries(draw: Any) -> QMatEntry:
    lattice = LatticeMetadata(
        a=draw(finite), b=draw(finite), c=draw(finite),
        alpha=draw(finite), beta=draw(finite), gamma=draw(finite),
        spacegroup_number=draw(st.none() | st.integers(1, 230)),
        metadata=draw(metadata),
    )
    return QMatEntry(
        reference=MaterialReference(
            provenance=SourceProvenance(
                primary=ExternalIdentifier(draw(text), draw(text), metadata=draw(metadata)),
                functional=draw(st.none() | text),
                code=draw(st.none() | text),
                metadata=draw(metadata),
            ),
            structure=StructureMetadata(
                draw(text), draw(text), draw(st.integers(0, 10**6)),
                draw(st.lists(text, max_size=5)), lattice, metadata=draw(metadata),
                sites=draw(st.lists(sites, max_size=4)),
            ),
        ),
        hamiltonian=HamiltonianMetadata(
            draw(st.integers(0, 10**9)),
            draw(st.booleans()),
            BasisMetadata(
                type=draw(text),
                cutoff_energy_ev=draw(st.none() | finite),
                num_plane_waves=draw(st.none() | st.integers(0, 10**9)),
                grid_dimensions=draw(
                    st.none() | st.tuples(*[st.integers(1, 999)] * 3)
                ),
                metadata=draw(metadata),
            ),
            num_bands=draw(st.none() | st.integers(0, 10**6)),
            metadata=draw(metadata),
        ),
        tags=draw(st.lists(text, max_size=4)),
    )


FIXTURE = json.loads((ROOT / "benchmarks/fixtures/LiCoO2.json").read_text())


def _paths(obj: Any, prefix: tuple[Any, ...] = ()) -> Any:
    yield prefix
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _paths(v, (*prefix, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _paths(v, (*prefix, i))


FIXTURE_PATHS = [p for p in _paths(FIXTURE) if p]

# ===================================================================== reader


@SETTINGS
@given(json_value)
def test_reader_accepts_or_raises_entry_format_error_only(value: Any) -> None:
    try:
        entry_from_dict(value)
    except EntryFormatError:
        pass


@SETTINGS
@given(st.sampled_from(FIXTURE_PATHS), json_value, st.sampled_from(["replace", "delete", "add"]))
def test_mutating_any_field_of_a_real_entry_never_crashes_the_reader(
    path: tuple[Any, ...], value: Any, mode: str
) -> None:
    d = copy.deepcopy(FIXTURE)
    node: Any = d
    for key in path[:-1]:
        node = node[key]
    if mode == "replace":
        node[path[-1]] = value
    elif mode == "delete":
        del node[path[-1]]
    elif isinstance(node, dict):
        node["__unexpected__"] = value
    try:
        entry_from_dict(d)
    except EntryFormatError:
        pass


@SETTINGS
@given(entries())
def test_round_trip_preserves_entry_and_hash(entry: QMatEntry) -> None:
    back = entry_from_dict(json.loads(json.dumps(to_dict(entry), allow_nan=False)))
    assert back == entry
    assert back.canonical_hash() == entry.canonical_hash()


@settings(max_examples=40, deadline=None, suppress_health_check=list(HealthCheck))
@given(entries())
def test_file_round_trip(entry: QMatEntry) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = write_entry_json(entry, Path(d) / "e.json")
        assert read_entry_json(p) == entry


# ======================================================================= hash


@SETTINGS
@given(entries(), metadata, st.lists(text, max_size=3))
def test_hash_ignores_everything_outside_its_eleven_fields(
    entry: QMatEntry, meta: dict[str, Any], tags: list[str]
) -> None:
    before = entry.canonical_hash()
    other = copy.deepcopy(entry)
    other.tags = tags
    other.exports = [ExportMetadata(framework="x", format="y")]
    other.reference.provenance.metadata = meta
    other.reference.provenance.retrieved_at = "2099-01-01"
    other.reference.provenance.code = "something else"
    other.reference.structure.metadata = meta
    other.hamiltonian.metadata = meta
    assert other.canonical_hash() == before


HASHED_FIELDS = {
    "source": lambda e: setattr(e.reference.provenance.primary, "source", "oqmd-x"),
    "identifier": lambda e: setattr(e.reference.provenance.primary, "identifier", "id-x"),
    "functional": lambda e: setattr(e.reference.provenance, "functional", "HSE06-x"),
    "formula_reduced": lambda e: setattr(e.reference.structure, "formula_reduced", "X9"),
    "spacegroup_number": lambda e: setattr(e.reference.structure.lattice, "spacegroup_number", 1),
    "num_electrons": lambda e: setattr(e.hamiltonian, "num_electrons", 10**9 + 7),
    "spin_polarized": lambda e: setattr(e.hamiltonian, "spin_polarized", not e.hamiltonian.spin_polarized),
    "basis_type": lambda e: setattr(e.hamiltonian.basis, "type", "gaussian-x"),
    "cutoff_energy_ev": lambda e: setattr(e.hamiltonian.basis, "cutoff_energy_ev", 12345.5),
    "num_bands": lambda e: setattr(e.hamiltonian, "num_bands", 10**6 + 3),
    "oracle_eta": lambda e: setattr(e.hamiltonian, "oracle", OracleMetadata(method="LCU", eta=0.123)),
}


@SETTINGS
@given(entries(), st.sampled_from(sorted(HASHED_FIELDS)))
def test_hash_changes_when_any_hashed_field_changes(entry: QMatEntry, field: str) -> None:
    before = entry.canonical_hash()
    other = copy.deepcopy(entry)
    HASHED_FIELDS[field](other)
    if to_dict(other) == to_dict(entry):
        return  # the generated entry already had that value
    assert other.canonical_hash() != before, field


def test_hash_is_identical_across_hash_seeds(tmp_path: Path) -> None:
    p = tmp_path / "e.json"
    p.write_text(json.dumps(FIXTURE))
    code = (
        "import sys; from qmatbridge.io import read_entry_json; "
        "print(read_entry_json(sys.argv[1]).canonical_hash())"
    )
    seen = set()
    for seed in ("0", "1", "random", "4242"):
        out = subprocess.run(
            [sys.executable, "-c", code, str(p)],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True, text=True, check=True,
        )
        seen.add(out.stdout.strip())
    assert len(seen) == 1


# ================================================================ converters

doc_keys = st.sampled_from([
    "structure", "lattice", "sites", "species", "element", "occu", "a", "b", "c", "alpha",
    "beta", "gamma", "symmetry", "number", "symbol", "crystal_system", "input", "incar",
    "parameters", "ENCUT", "NELECT", "ISPIN", "abc", "task_id", "run_type", "hubbards",
])
doc_value = st.recursive(
    json_scalar,
    lambda c: st.lists(c, max_size=3) | st.dictionaries(doc_keys, c, max_size=5),
    max_leaves=14,
)
SMALL_CELL = LatticeMetadata(a=0.5, b=0.5, c=0.5, alpha=90, beta=90, gamma=90)


@SETTINGS
@given(doc_value)
def test_structure_converter_raises_only_value_error(d: Any) -> None:
    try:
        structure_from_mp_doc(d)
    except ValueError:
        pass


@SETTINGS
@given(doc_value)
def test_hamiltonian_converter_raises_only_value_error(d: Any) -> None:
    structure = StructureMetadata("Si", "Si", 1, ["Si"], SMALL_CELL)
    try:
        hamiltonian_from_mp_task_doc(d, structure)
    except ValueError:
        pass


# ================================================================ plane waves

cells = st.builds(
    LatticeMetadata,
    a=st.floats(2.5, 9), b=st.floats(2.5, 9), c=st.floats(2.5, 9),
    alpha=st.floats(55, 125), beta=st.floats(55, 125), gamma=st.floats(55, 125),
)


def _valid(lat: LatticeMetadata) -> bool:
    try:
        cell_volume(lat)
    except ValueError:
        return False
    return True


@SETTINGS
@given(cells, st.floats(30, 120), st.floats(0.7, 1.6))
def test_scaling_law(lat: LatticeMetadata, ecut: float, s: float) -> None:
    """Scaling the cell by s is equivalent to scaling the cutoff by s^2."""
    if not _valid(lat):
        return
    scaled = LatticeMetadata(
        a=lat.a * s, b=lat.b * s, c=lat.c * s, alpha=lat.alpha, beta=lat.beta, gamma=lat.gamma
    )
    n1, n2 = num_plane_waves_exact(scaled, ecut), num_plane_waves_exact(lat, ecut * s * s)
    assert abs(n1 - n2) <= max(2, math.ceil(0.001 * n1))


@SETTINGS
@given(cells, st.floats(30, 100))
def test_count_is_positive_and_monotonic_in_cutoff(lat: LatticeMetadata, ecut: float) -> None:
    if not _valid(lat):
        return
    low, high = num_plane_waves_exact(lat, ecut), num_plane_waves_exact(lat, ecut * 1.5)
    assert 1 <= low <= high


@SETTINGS
@given(cells, st.floats(30, 100))
def test_count_is_invariant_under_cyclic_axis_permutation(lat: LatticeMetadata, ecut: float) -> None:
    """The same lattice described with its axes cycled has the same plane waves."""
    if not _valid(lat):
        return
    cycled = LatticeMetadata(
        a=lat.b, b=lat.c, c=lat.a, alpha=lat.beta, beta=lat.gamma, gamma=lat.alpha
    )
    assert num_plane_waves_exact(lat, ecut) == num_plane_waves_exact(cycled, ecut)


@pytest.mark.parametrize("seed", range(5))
def test_exact_matches_an_independent_brute_force_count(seed: int) -> None:
    """Cross-check against a deliberately different, larger-box enumeration."""
    import random

    rng = random.Random(seed)
    lat = LatticeMetadata(
        a=rng.uniform(3, 7), b=rng.uniform(3, 7), c=rng.uniform(3, 7),
        alpha=rng.uniform(60, 120), beta=rng.uniform(60, 120), gamma=rng.uniform(60, 120),
    )
    if not _valid(lat):
        pytest.skip("degenerate cell")
    ecut = rng.uniform(40, 90)
    assert num_plane_waves_exact(lat, ecut) == _brute_force(lat, ecut)


def _brute_force(lat: LatticeMetadata, ecut: float) -> int:
    import itertools

    from qmatbridge.basis import HBAR2_OVER_2M_EV_A2 as C

    ca, cb, cg = (math.cos(math.radians(x)) for x in (lat.alpha, lat.beta, lat.gamma))
    sg = math.sin(math.radians(lat.gamma))
    a1 = (lat.a, 0.0, 0.0)
    a2 = (lat.b * cg, lat.b * sg, 0.0)
    cx, cy = lat.c * cb, lat.c * (ca - cb * cg) / sg
    a3 = (cx, cy, math.sqrt(lat.c**2 - cx**2 - cy**2))
    (a, b, c), (d, e, f), (g, h, i) = a1, a2, a3
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    inv = [
        [(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
        [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
        [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det],
    ]
    recip = [[2 * math.pi * inv[r][s] for s in range(3)] for r in range(3)]
    kc2 = ecut / C
    lim = [int(kc2**0.5 * math.sqrt(sum(x * x for x in v)) / (2 * math.pi)) + 3 for v in (a1, a2, a3)]
    n = 0
    for p, q, r in itertools.product(*(range(-m, m + 1) for m in lim)):
        g3 = [recip[k][0] * p + recip[k][1] * q + recip[k][2] * r for k in range(3)]
        n += g3[0] ** 2 + g3[1] ** 2 + g3[2] ** 2 <= kc2
    return n


# ================================================================== geometry


def _with_sites(entry: QMatEntry, new: list[SiteMetadata]) -> QMatEntry:
    other = copy.deepcopy(entry)
    other.reference.structure.sites = new
    return other


@SETTINGS
@given(entries(), st.lists(grid_sites, min_size=1, max_size=6), st.randoms(use_true_random=False))
def test_hash_does_not_depend_on_site_order(
    entry: QMatEntry, new: list[SiteMetadata], rnd: Any
) -> None:
    shuffled = list(new)
    rnd.shuffle(shuffled)
    assert _with_sites(entry, new).canonical_hash() == _with_sites(entry, shuffled).canonical_hash()


@SETTINGS
@given(entries(), st.lists(grid_sites, min_size=1, max_size=6), st.integers(-4, 4), st.integers(-4, 4), st.integers(-4, 4))
def test_hash_is_invariant_to_whole_cell_translations_of_coordinates(
    entry: QMatEntry, new: list[SiteMetadata], i: int, j: int, k: int
) -> None:
    moved = [SiteMetadata(s.element, (s.frac_coords[0] + i, s.frac_coords[1] + j, s.frac_coords[2] + k)) for s in new]
    assert _with_sites(entry, new).canonical_hash() == _with_sites(entry, moved).canonical_hash()


@SETTINGS
@given(entries(), st.lists(grid_sites, min_size=1, max_size=6), st.data())
def test_moving_one_atom_by_a_resolvable_amount_changes_the_hash(
    entry: QMatEntry, new: list[SiteMetadata], data: Any
) -> None:
    index = data.draw(st.integers(0, len(new) - 1))
    axis = data.draw(st.integers(0, 2))
    shift = data.draw(st.sampled_from([0.001, 0.01, 0.1, 0.3]))
    coords = list(new[index].frac_coords)
    coords[axis] = (coords[axis] + shift) % 1.0
    moved = list(new)
    moved[index] = SiteMetadata(new[index].element, (coords[0], coords[1], coords[2]))
    if sorted(map(repr, moved)) == sorted(map(repr, new)):
        return  # the move produced an identical multiset of sites
    assert _with_sites(entry, new).canonical_hash() != _with_sites(entry, moved).canonical_hash()


@SETTINGS
@given(entries())
def test_clearing_the_sites_restores_the_eleven_field_hash(entry: QMatEntry) -> None:
    """Entries without positions hash only the original eleven fields (option B)."""
    bare = _with_sites(entry, [])
    import hashlib

    prov, struct, ham = bare.reference.provenance, bare.reference.structure, bare.hamiltonian
    core = {
        "source": prov.primary.source, "identifier": prov.primary.identifier,
        "functional": prov.functional, "formula_reduced": struct.formula_reduced,
        "spacegroup_number": struct.lattice.spacegroup_number, "num_electrons": ham.num_electrons,
        "spin_polarized": ham.spin_polarized, "basis_type": ham.basis.type,
        "cutoff_energy_ev": ham.basis.cutoff_energy_ev, "num_bands": ham.num_bands,
        "oracle_eta": ham.oracle.eta if ham.oracle is not None else None,
    }
    assert bare.canonical_hash() == hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()
