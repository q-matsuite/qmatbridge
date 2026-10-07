"""Atomic positions in the schema (0.2) and what they do to ``canonical_hash()``.

The policy (Discussion #24, option B): entries WITHOUT positions keep exactly their
0.2.x hash; entries WITH positions also hash the lattice and the sites.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from qmatbridge.adapters.materials_project import structure_from_mp_doc
from qmatbridge.io import (
    SUPPORTED_SCHEMA_VERSIONS,
    EntryFormatError,
    entry_from_dict,
    read_entry_json,
    to_dict,
    write_entry_json,
)
from qmatbridge.schema import QMatEntry, SiteMetadata, _fixed6, _frac6, _geometry_core

ROOT = Path(__file__).resolve().parents[2]

#: canonical_hash() of each Tier-1 entry as published in 0.2.0, i.e. WITHOUT positions.
HASHES_WITHOUT_POSITIONS = {
    "Si": "f0393a56115a4f225601344df9e4a817186544ad0bb420833e982773cca93bc5",
    "GaN": "7614a23cc06cd107ca2b3208c64bec5bd46cbe870e80b8e5354f9e15af822ae4",
    "LiCoO2": "5de4b21d06c950b58b1f93a27c9ff8e8d037b3a513ec922d5e598df94a29e250",
    "LiFePO4": "565d3a007d6c4496ce88165ff41595128d33ae1196439ac6677e04f87f9ba8d0",
    "NaCl": "6e0801483495b05ab4459435931a65c7a74f8fac2a3151e2e1fd2002ec6b5c45",
    "BaTiO3": "186c3c6f7613e4663f1ce19d9f1b72088e7040ed1e5f751ee42811282101a650"
}


def fixture(key: str) -> QMatEntry:
    return read_entry_json(ROOT / "benchmarks/fixtures" / f"{key}.json")


def with_sites(entry: QMatEntry, sites: list[SiteMetadata]) -> QMatEntry:
    e = copy.deepcopy(entry)
    e.reference.structure.sites = sites
    return e


def si() -> QMatEntry:
    return fixture("Si")


# ------------------------------------------------------- backward compatibility


@pytest.mark.parametrize("key", sorted(HASHES_WITHOUT_POSITIONS))
def test_entries_without_positions_keep_their_published_hash(key: str) -> None:
    """The guarantee behind option B: stripping the positions reproduces the 0.2.0 hash."""
    e = fixture(key)
    assert e.reference.structure.sites, "fixtures are expected to carry positions"
    stripped = with_sites(e, [])
    assert stripped.canonical_hash() == HASHES_WITHOUT_POSITIONS[key]
    assert e.canonical_hash() != HASHES_WITHOUT_POSITIONS[key], "geometry must change the hash"


def test_an_entry_without_sites_hashes_the_original_eleven_fields_only() -> None:
    import hashlib

    e = with_sites(si(), [])
    core = {
        "source": "materials_project", "identifier": "mp-149", "functional": "PBE",
        "formula_reduced": "Si", "spacegroup_number": 227, "num_electrons": 8,
        "spin_polarized": True, "basis_type": "plane_wave", "cutoff_energy_ev": 520.0,
        "num_bands": None, "oracle_eta": None,
    }
    assert e.canonical_hash() == hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ the geometry


def test_site_order_does_not_matter() -> None:
    e = fixture("LiFePO4")
    reversed_ = with_sites(e, list(reversed(e.reference.structure.sites)))
    assert reversed_.canonical_hash() == e.canonical_hash()


def test_coordinates_are_wrapped_into_the_unit_cell() -> None:
    base = [SiteMetadata("Si", (0.0, 0.0, 0.0)), SiteMetadata("Si", (0.25, 0.25, 0.25))]
    shifted = [SiteMetadata("Si", (1.0, -1.0, 2.0)), SiteMetadata("Si", (1.25, -0.75, 0.25))]
    assert with_sites(si(), base).canonical_hash() == with_sites(si(), shifted).canonical_hash()


def test_noise_below_the_rounding_resolution_is_ignored() -> None:
    base = [SiteMetadata("Si", (0.0, 0.0, 0.0)), SiteMetadata("Si", (0.25, 0.25, 0.25))]
    noisy = [SiteMetadata("Si", (1e-10, -1e-10, 0.0)), SiteMetadata("Si", (0.25 + 1e-9, 0.25 - 1e-9, 0.25))]
    assert with_sites(si(), base).canonical_hash() == with_sites(si(), noisy).canonical_hash()


@pytest.mark.parametrize("change", ["move an atom", "swap an element", "drop an atom", "stretch a"])
def test_real_geometry_changes_change_the_hash(change: str) -> None:
    e = si()
    h = e.canonical_hash()
    other = copy.deepcopy(e)
    s = other.reference.structure
    if change == "move an atom":
        s.sites[1] = SiteMetadata("Si", (0.251, 0.25, 0.25))
    elif change == "swap an element":
        s.sites[1] = SiteMetadata("Ge", s.sites[1].frac_coords)
    elif change == "drop an atom":
        s.sites = s.sites[:1]
    else:
        s.lattice.a *= 1.001
    assert other.canonical_hash() != h


def test_a_larger_lattice_no_longer_collides() -> None:
    """Found by the 0.2.0 stress test: a 50% larger lattice used to give the same hash."""
    e = si()
    big = copy.deepcopy(e)
    for k in ("a", "b", "c"):
        setattr(big.reference.structure.lattice, k, getattr(big.reference.structure.lattice, k) * 1.5)
    assert big.canonical_hash() != e.canonical_hash()
    # ...while an entry that records no positions still cannot tell them apart
    assert with_sites(big, []).canonical_hash() == with_sites(e, []).canonical_hash()


def test_non_finite_geometry_cannot_be_hashed() -> None:
    for bad in (float("nan"), float("inf")):
        e = with_sites(si(), [SiteMetadata("Si", (bad, 0.0, 0.0))])
        with pytest.raises(ValueError, match="non-finite"):
            e.canonical_hash()
    e = si()
    e.reference.structure.lattice.a = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        e.canonical_hash()


def test_canonical_geometry_text_is_stable() -> None:
    s = si().reference.structure
    g = _geometry_core(s)
    assert all(re.fullmatch(r"\d+\.\d{6}", v) for v in g["lattice"])
    assert g["sites"] == sorted(g["sites"])
    assert all(re.fullmatch(r"[01]\.\d{6}", c) and c != "1.000000" for _, xyz in g["sites"] for c in xyz)


@pytest.mark.parametrize(
    ("value", "fixed", "frac"),
    [
        (0.0078125, "0.007813", "0.007813"),    # exact tie: away from zero, as JavaScript toFixed
        (1 / 128, "0.007813", "0.007813"),
        (0.0234375, "0.023438", "0.023438"),
        (-0.0000004, "0.000000", "0.000000"),   # no negative zero
        (-0.25, "-0.250000", "0.750000"),
        (1.0, "1.000000", "0.000000"),
        (0.9999995, "1.000000", "0.000000"),    # rounds up to 1: wraps to 0
        (1e22, "10000000000000000000000.000000", "0.000000"),
    ],
)
def test_fixed_decimal_rounding(value: float, fixed: str, frac: str) -> None:
    assert _fixed6(value) == fixed
    assert _frac6(value) == frac


# ------------------------------------------------------- schema version and I/O


def test_new_entries_use_schema_0_2_and_readers_accept_both_versions(tmp_path: Path) -> None:
    e = si()
    assert QMatEntry.__dataclass_fields__["schema_version"].default == "0.3"
    assert SUPPORTED_SCHEMA_VERSIONS == ("0.1", "0.2", "0.3")
    d = to_dict(e)
    for version in ("0.1", "0.2", "0.3"):
        d["schema_version"] = version
        assert entry_from_dict(d).schema_version == version
    d["schema_version"] = "0.4"
    with pytest.raises(EntryFormatError, match="schema_version"):
        entry_from_dict(d)


def test_an_old_file_without_sites_still_loads() -> None:
    d = to_dict(si())
    del d["reference"]["structure"]["sites"]
    d["schema_version"] = "0.1"
    e = entry_from_dict(d)
    assert e.reference.structure.sites == []
    assert e.canonical_hash() == HASHES_WITHOUT_POSITIONS["Si"]


def test_sites_round_trip_through_a_file(tmp_path: Path) -> None:
    e = fixture("BaTiO3")
    back = read_entry_json(write_entry_json(e, tmp_path / "e.json"))
    assert back == e and back.canonical_hash() == e.canonical_hash()
    assert isinstance(back.reference.structure.sites[0].frac_coords, tuple)


@pytest.mark.parametrize("bad", [[0.0, 0.0], [0.0, 0.0, 0.0, 0.0], "abc", [0.0, "x", 0.0], None])
def test_malformed_positions_are_entry_format_errors(bad: Any) -> None:
    d = to_dict(si())
    d["reference"]["structure"]["sites"][0]["frac_coords"] = bad
    with pytest.raises(EntryFormatError):
        entry_from_dict(d)


# --------------------------------------------------------- Materials Project docs


def mp_doc(**site_extra: Any) -> dict[str, Any]:
    site = {"species": [{"element": "Si", "occu": 1}], **site_extra}
    return {"structure": {"lattice": dict(a=3.8, b=3.8, c=3.8, alpha=60.0, beta=60.0, gamma=60.0),
                          "sites": [site, copy.deepcopy(site)]}}


def test_adapter_records_positions_when_every_site_has_them() -> None:
    d = mp_doc(abc=[0.0, 0.0, 0.0])
    d["structure"]["sites"][1]["abc"] = [0.25, 0.25, 0.25]
    s = structure_from_mp_doc(d)
    assert [x.element for x in s.sites] == ["Si", "Si"]
    assert s.sites[1].frac_coords == (0.25, 0.25, 0.25)


def test_documents_without_positions_still_convert_with_empty_sites() -> None:
    assert structure_from_mp_doc(mp_doc()).sites == []


def test_partial_positions_are_rejected_not_half_recorded() -> None:
    d = mp_doc(abc=[0.0, 0.0, 0.0])
    del d["structure"]["sites"][1]["abc"]
    with pytest.raises(ValueError, match="only 1 of 2 sites"):
        structure_from_mp_doc(d)


@pytest.mark.parametrize("abc", [[0.0, 0.0], [0.0, 0.0, 0.0, 0.0], "abc", [0, "x", 0], [float("nan"), 0, 0], [True, 0, 0], 5])
def test_malformed_positions_in_mp_documents_are_value_errors(abc: Any) -> None:
    with pytest.raises(ValueError):
        structure_from_mp_doc(mp_doc(abc=abc))


# -------------------------------- the website's JavaScript must agree with Python

NODE = shutil.which("node")


def _js_hasher() -> str:
    html = (ROOT / "website/index.template.html").read_text()
    sha = html[html.index("const K = new Uint32Array"): html.index("/* ---------- identicon from a hash")]
    rules = html[html.index("// Mirrors python: json.dumps"): html.index("/* ---------- crystal viewer")]
    return (
        sha + rules + "\n"
        "const chunks = []; process.stdin.on('data', c => chunks.push(c));\n"
        "process.stdin.on('end', () => { const entries = JSON.parse(Buffer.concat(chunks).toString());\n"
        "  console.log(JSON.stringify(entries.map(e => sha256hex(blob(coreOf({ entry: e })))))); });\n"
    )


def js_hashes(entries: list[QMatEntry], tmp_path: Path) -> list[str]:
    script = tmp_path / "hash.js"
    script.write_text(_js_hasher())
    out = subprocess.run([NODE, str(script)], input=json.dumps([to_dict(e) for e in entries]),
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)  # type: ignore[no-any-return]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_website_javascript_matches_python_on_the_fixtures(tmp_path: Path) -> None:
    entries = [fixture(k) for k in HASHES_WITHOUT_POSITIONS]
    entries += [with_sites(e, []) for e in entries]  # and without positions
    assert js_hashes(entries, tmp_path) == [e.canonical_hash() for e in entries]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_website_javascript_matches_python_on_adversarial_coordinates(tmp_path: Path) -> None:
    import random

    rng = random.Random(7)
    nasty = [0.0, 1.0, -1.0, 0.5, 1 / 128, 3 / 128, 5 / 1024, 0.0078125, 0.9999995, 0.9999994,
             -0.0000004, -1e-12, 1e-12, 2.5e-7, 1e-6, 7.000001, -3.25, 123.456789, 0.1, 0.2, 0.3, 1 / 3, 2 / 3]
    entries = []
    for i in range(60):
        coords = [rng.choice(nasty) if rng.random() < 0.6 else rng.uniform(-3, 3) for _ in range(9)]
        sites = [SiteMetadata(rng.choice(["Si", "O", "Li", "Fe"]), tuple(coords[j:j + 3])) for j in (0, 3, 6)]
        e = with_sites(si(), sites)
        lat = e.reference.structure.lattice
        lat.a, lat.b, lat.c = (rng.choice([3.849, 1 / 128, 12.0000005, 5.0, 4.0078125]) for _ in range(3))
        lat.alpha, lat.beta, lat.gamma = (rng.choice([60.0, 90.0, 120.0, 89.9999995, 33.25407937825511]) for _ in range(3))
        entries.append(e)
    assert js_hashes(entries, tmp_path) == [e.canonical_hash() for e in entries]
