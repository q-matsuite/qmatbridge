"""Tests for reading entries back: from_dict, entry_from_dict, read_entry_json."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from qmatbridge.io import (
    SUPPORTED_SCHEMA_VERSIONS,
    EntryFormatError,
    entry_from_dict,
    from_dict,
    read_entry_json,
    to_dict,
    write_entry_json,
)
from qmatbridge.schema import (
    BasisMetadata,
    ExportMetadata,
    LatticeMetadata,
    OracleMetadata,
    QMatEntry,
    TermMetadata,
)

ROOT = Path(__file__).resolve().parents[2]


# ----------------------------------------------------------------- round trips


def test_round_trip_minimal(minimal_entry: QMatEntry, tmp_path: Path) -> None:
    path = write_entry_json(minimal_entry, tmp_path / "e.json")
    back = read_entry_json(path)
    assert back == minimal_entry
    assert back.canonical_hash() == minimal_entry.canonical_hash()


def test_round_trip_fully_populated(minimal_entry: QMatEntry, tmp_path: Path) -> None:
    """Exercise nested lists, optional dataclasses, tuples and free-form dicts."""
    e = minimal_entry
    e.hamiltonian.basis = BasisMetadata(
        type="plane_wave",
        cutoff_energy_ev=520.0,
        num_plane_waves=1067,
        grid_dimensions=(24, 24, 24),
        metadata={"nested": {"x": [1, 2.5, None, "s"]}},
    )
    e.hamiltonian.terms = [TermMetadata(name="kinetic", lambda_one_norm=1.5)]
    e.hamiltonian.oracle = OracleMetadata(
        method="LCU",
        eta=8.0,
        terms=[TermMetadata(name="U", coefficient_labels=["a", "b"])],
        complexity={"toffoli": "O(N^(1/3))"},
    )
    e.exports = [ExportMetadata(framework="openfermion", format="json")]
    e.tags = ["a", "b"]
    path = write_entry_json(e, tmp_path / "full.json")
    back = read_entry_json(path)
    assert back == e
    assert isinstance(back.hamiltonian.basis.grid_dimensions, tuple)  # not a list
    assert back.canonical_hash() == e.canonical_hash()


def test_silicon_example_round_trips() -> None:
    back = read_entry_json(ROOT / "examples/silicon_entry.json")
    assert back.reference.structure.formula_reduced == "Si"
    assert to_dict(back) == json.loads((ROOT / "examples/silicon_entry.json").read_text())


@pytest.mark.parametrize("key", ["Si", "GaN", "LiCoO2"])
def test_committed_fixtures_load_and_match_site_hash(key: str) -> None:
    """The fixtures load, and their hash equals the one the website displays."""
    fx = ROOT / "benchmarks/fixtures" / f"{key}.json"
    site = ROOT / "website/data/examples.json"
    if not fx.exists() or not site.exists():
        pytest.skip("fixtures not generated")
    entry = read_entry_json(fx)
    rec = next(r for r in json.loads(site.read_text()) if r["key"] == key)
    assert entry.canonical_hash() == rec["hash"]
    assert to_dict(entry) == json.loads(fx.read_text())


def test_from_dict_generic_dataclass() -> None:
    lat = LatticeMetadata(a=3.8, b=3.8, c=3.8, alpha=60, beta=60, gamma=60)
    assert from_dict(LatticeMetadata, to_dict(lat)) == lat


def test_int_is_accepted_for_float_fields() -> None:
    d = to_dict(LatticeMetadata(a=3, b=3, c=3, alpha=60, beta=60, gamma=60))
    back = from_dict(LatticeMetadata, d)
    assert back.a == 3.0 and isinstance(back.a, float)


def test_hash_is_stable_when_cutoff_written_as_int(minimal_entry: QMatEntry) -> None:
    """JSON `520` and `520.0` must give the same entry, hence the same hash."""
    d = to_dict(minimal_entry)
    h = d["hamiltonian"]["basis"]
    h["cutoff_energy_ev"] = 520
    other = copy.deepcopy(d)
    other["hamiltonian"]["basis"]["cutoff_energy_ev"] = 520.0
    assert entry_from_dict(d).canonical_hash() == entry_from_dict(other).canonical_hash()


# ----------------------------------------------------------------- rejections


def good(minimal_entry: QMatEntry) -> dict:
    return to_dict(minimal_entry)  # type: ignore[no-any-return]


def test_unsupported_schema_version(minimal_entry: QMatEntry) -> None:
    d = good(minimal_entry)
    d["schema_version"] = "9.9"
    with pytest.raises(EntryFormatError, match=r"schema_version.*9\.9.*0\.1"):
        entry_from_dict(d)


def test_missing_schema_version_defaults_to_current(minimal_entry: QMatEntry) -> None:
    d = good(minimal_entry)
    del d["schema_version"]
    assert entry_from_dict(d).schema_version in SUPPORTED_SCHEMA_VERSIONS


def test_unknown_field_is_rejected_not_dropped(minimal_entry: QMatEntry) -> None:
    d = good(minimal_entry)
    d["hamiltonian"]["basis"]["cutoff_ev"] = 500.0  # typo'd name
    with pytest.raises(EntryFormatError, match=r"hamiltonian\.basis.*cutoff_ev"):
        entry_from_dict(d)


def test_missing_required_field_names_the_path(minimal_entry: QMatEntry) -> None:
    d = good(minimal_entry)
    del d["hamiltonian"]["num_electrons"]
    with pytest.raises(EntryFormatError, match=r"hamiltonian\.num_electrons.*missing"):
        entry_from_dict(d)


@pytest.mark.parametrize(
    ("where", "value", "message"),
    [
        (("hamiltonian", "num_electrons"), "8", "expected an integer, got str"),
        (("hamiltonian", "num_electrons"), True, "expected an integer, got bool"),
        (("hamiltonian", "num_electrons"), 8.5, "expected an integer, got float"),
        (("hamiltonian", "spin_polarized"), 1, "expected a boolean, got int"),
        (("hamiltonian", "basis", "cutoff_energy_ev"), "520", "expected a number"),
        (("hamiltonian", "basis", "cutoff_energy_ev"), True, "expected a number, got bool"),
        (("reference", "structure", "species"), "Si", "expected a list, got str"),
        (("reference", "structure", "species"), [1], r"species\[0\]: expected a string"),
        (("tags",), {"a": 1}, "expected a list, got dict"),
        (("hamiltonian", "basis", "metadata"), [1], "expected an object, got list"),
        (("hamiltonian", "basis", "grid_dimensions"), [1, 2], "expected 3 items, got 2"),
        (("reference", "structure"), None, "expected an object, got NoneType"),
    ],
)
def test_wrong_types_are_rejected(
    minimal_entry: QMatEntry, where: tuple[str, ...], value: object, message: str
) -> None:
    d = good(minimal_entry)
    node = d
    for k in where[:-1]:
        node = node[k]
    node[where[-1]] = value
    with pytest.raises(EntryFormatError, match=message):
        entry_from_dict(d)


def test_top_level_must_be_an_object() -> None:
    with pytest.raises(EntryFormatError, match="expected an object, got list"):
        entry_from_dict([1, 2])


# ----------------------------------------------------------------------- files


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_entry_json(tmp_path / "nope.json")


def test_invalid_json_names_the_file(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(EntryFormatError, match=r"bad\.json.*not valid JSON"):
        read_entry_json(p)


def test_schema_error_names_the_file(tmp_path: Path, minimal_entry: QMatEntry) -> None:
    d = good(minimal_entry)
    d["hamiltonian"]["num_electrons"] = "eight"
    p = tmp_path / "wrong.json"
    p.write_text(json.dumps(d))
    with pytest.raises(EntryFormatError, match=r"wrong\.json: hamiltonian\.num_electrons"):
        read_entry_json(p)


def test_entry_format_error_is_a_value_error() -> None:
    assert issubclass(EntryFormatError, ValueError)
