"""Cross-database deduplication."""

from __future__ import annotations

import copy

import pytest

from qmatbridge.dedup import (
    deduplicate,
    external_identifiers,
    find_duplicates,
    structures_match,
)
from qmatbridge.io import read_entry_json
from qmatbridge.schema import ExternalIdentifier, QMatEntry, SiteMetadata


def _fixture(name: str) -> QMatEntry:
    return read_entry_json(f"benchmarks/fixtures/{name}.json")


def _with(
    entry: QMatEntry,
    *,
    source: str,
    identifier: str,
    scale: float = 1.0,
    extra: list[tuple[str, str]] = (),  # type: ignore[assignment]
) -> QMatEntry:
    e = copy.deepcopy(entry)
    prov = e.reference.provenance
    prov.primary = ExternalIdentifier(source, identifier)
    prov.additional_ids = [ExternalIdentifier(s, i) for s, i in extra]
    lat = e.reference.structure.lattice
    lat.a, lat.b, lat.c = lat.a * scale, lat.b * scale, lat.c * scale
    return e


def _cell(entry: QMatEntry, a: float, alpha: float, atoms: list) -> QMatEntry:
    e = copy.deepcopy(entry)
    s = e.reference.structure
    s.lattice.a = s.lattice.b = s.lattice.c = a
    s.lattice.alpha = s.lattice.beta = s.lattice.gamma = alpha
    s.sites = [SiteMetadata(el, pos) for el, pos in atoms]
    s.species = [el for el, _ in atoms]
    s.num_sites = len(atoms)
    return e


def _diamond_conventional(entry: QMatEntry, a: float = 5.43) -> QMatEntry:
    fcc = [(0, 0, 0), (0, 0.5, 0.5), (0.5, 0, 0.5), (0.5, 0.5, 0)]
    atoms = [("Si", p) for p in fcc]
    atoms += [("Si", tuple(x + 0.25 for x in p)) for p in fcc]
    return _cell(entry, a, 90.0, atoms)


@pytest.fixture
def si() -> QMatEntry:
    return _fixture("Si")


# --- geometry ---------------------------------------------------------------


def test_primitive_and_conventional_cells_of_one_crystal_match(si: QMatEntry) -> None:
    conventional = _diamond_conventional(si)
    # the fixture's primitive cell is a = 3.867 A at 60 degrees: a_conv = a_prim * sqrt(2)
    assert structures_match(si, conventional, rtol=0.01)
    assert conventional.reference.structure.num_sites == 8


def test_match_ignores_origin_and_atom_order(si: QMatEntry) -> None:
    moved = copy.deepcopy(si)
    s = moved.reference.structure
    s.sites = [
        SiteMetadata(x.element, tuple((c + 0.37) % 1.0 for c in x.frac_coords))
        for x in reversed(s.sites)
    ]
    assert structures_match(si, moved)


def test_a_two_percent_lattice_difference_matches_by_default_not_when_tight(
    si: QMatEntry,
) -> None:
    other = _with(si, source="alexandria", identifier="x", scale=1.02)
    assert structures_match(si, other)
    assert not structures_match(si, other, rtol=0.005)


def test_different_phases_of_one_composition_do_not_match() -> None:
    nacl = _fixture("NaCl")
    # rocksalt (as in the fixture) against a zincblende NaCl of similar density
    zb = _cell(nacl, 5.0, 60.0, [("Na", (0, 0, 0)), ("Cl", (0.25, 0.25, 0.25))])
    assert not structures_match(nacl, zb)


def test_different_formulas_never_match(si: QMatEntry) -> None:
    assert not structures_match(si, _fixture("NaCl"))


def test_geometry_needs_positions(si: QMatEntry) -> None:
    bare = copy.deepcopy(si)
    bare.reference.structure.sites = []
    with pytest.raises(ValueError, match="atomic positions"):
        structures_match(si, bare)


# --- identifiers ------------------------------------------------------------


def test_identifiers_include_primary_and_cross_references(si: QMatEntry) -> None:
    e = _with(
        si, source="materials_project", identifier="mp-149", extra=[("icsd", "51688")]
    )
    assert external_identifiers(e) >= {
        ("materials_project", "mp-149"),
        ("icsd", "51688"),
    }


def test_an_optimade_entry_is_known_under_the_provider_name(si: QMatEntry) -> None:
    e = _with(si, source="optimade:mp", identifier="mp:mp-149")
    assert ("materials_project", "mp-149") in external_identifiers(e)


# --- grouping ---------------------------------------------------------------


def test_shared_icsd_number_groups_entries_with_no_positions(si: QMatEntry) -> None:
    a = _with(
        si, source="materials_project", identifier="mp-149", extra=[("icsd", "51688")]
    )
    b = _with(si, source="oqmd", identifier="oqmd-1", extra=[("icsd", "51688")])
    for e in (a, b):
        e.reference.structure.sites = []
    (group,) = find_duplicates([a, b], use_geometry=False)
    assert group.indices == [0, 1]
    assert group.links[0].kind == "shared_identifier"
    assert group.links[0].shared == [("icsd", "51688")]
    assert group.links[0].geometry_agrees is None


def test_geometry_alone_finds_a_duplicate_with_no_shared_id(si: QMatEntry) -> None:
    a = si
    b = _with(si, source="alexandria", identifier="agm002", scale=1.015)
    c = _fixture("NaCl")
    (group,) = find_duplicates([a, c, b])
    assert group.indices == [0, 2]
    assert group.links[0].kind == "geometry"


def test_grouping_is_transitive(si: QMatEntry) -> None:
    a = _with(
        si, source="materials_project", identifier="mp-149", extra=[("icsd", "1")]
    )
    b = _with(
        si, source="oqmd", identifier="oqmd-1", extra=[("icsd", "1"), ("cod", "9")]
    )
    c = _with(si, source="cod", identifier="9")
    for e in (a, b, c):
        e.reference.structure.sites = []
    (group,) = find_duplicates([a, b, c], use_geometry=False)
    assert group.indices == [0, 1, 2]


def test_an_identifier_shared_by_different_structures_is_flagged(si: QMatEntry) -> None:
    a = _with(si, source="materials_project", identifier="mp-1", extra=[("icsd", "7")])
    b = _with(
        _fixture("NaCl"), source="oqmd", identifier="oqmd-2", extra=[("icsd", "7")]
    )
    # different formulas: they are linked by the id but the geometry says no
    (group,) = find_duplicates([a, b])
    assert [lk.geometry_agrees for lk in group.conflicts] == [False]


def test_distinct_materials_make_no_groups() -> None:
    names = ["Si", "GaN", "NaCl", "BaTiO3", "LiCoO2"]
    assert find_duplicates([_fixture(n) for n in names]) == []


def test_deduplicate_keeps_one_per_material_and_honours_prefer(si: QMatEntry) -> None:
    a = si
    b = _with(si, source="alexandria", identifier="agm002", scale=1.01)
    b.reference.provenance.functional = "PBEsol"
    other = _fixture("NaCl")
    assert deduplicate([a, other, b]) == [a, other]
    kept = deduplicate(
        [a, other, b], prefer=lambda e: e.reference.provenance.functional != "PBEsol"
    )
    assert kept == [other, b]
