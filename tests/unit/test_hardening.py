"""Regression tests for the defects found by stress-testing the published 0.2.0.

Each test pins one finding: data loss on failed writes, unbounded plane-wave
work, reader and converter robustness against hostile input, decode performance,
and packaging.
"""

from __future__ import annotations

import collections
import enum
import json
import re
import sys
import time
import typing
from pathlib import Path
from typing import Any

import pytest

import qmatbridge
from qmatbridge.adapters import materials_project as mp
from qmatbridge.adapters.materials_project import (
    functional_from_mp_task_doc,
    hamiltonian_from_mp_task_doc,
    structure_from_mp_doc,
)
from qmatbridge.basis import (
    DEFAULT_MAX_CANDIDATES,
    num_plane_waves_estimate,
    num_plane_waves_exact,
    num_plane_waves_from_ecut,
)
from qmatbridge.io import (
    EntryFormatError,
    _schema_of,
    entry_from_dict,
    read_entry_json,
    to_dict,
    write_entry_json,
)
from qmatbridge.schema import LatticeMetadata, QMatEntry, TermMetadata

ROOT = Path(__file__).resolve().parents[2]


def cubic(a: float) -> LatticeMetadata:
    return LatticeMetadata(a=a, b=a, c=a, alpha=90.0, beta=90.0, gamma=90.0)


# ============================================================ write_entry_json


class _Unserialisable:
    pass


def test_failed_write_never_destroys_an_existing_file(
    minimal_entry: QMatEntry, tmp_path: Path
) -> None:
    """Found: a TypeError mid-write truncated the previous good file."""
    out = write_entry_json(minimal_entry, tmp_path / "e.json")
    good = out.read_text()
    minimal_entry.hamiltonian.metadata = {"x": _Unserialisable()}
    with pytest.raises(TypeError):
        write_entry_json(minimal_entry, out)
    assert out.read_text() == good
    assert [p.name for p in tmp_path.iterdir()] == ["e.json"]  # no temp litter


def test_nan_and_infinity_are_refused_not_written(
    minimal_entry: QMatEntry, tmp_path: Path
) -> None:
    """Found: NaN was written, producing non-standard JSON other tools reject."""
    out = write_entry_json(minimal_entry, tmp_path / "e.json")
    good = out.read_text()
    for bad in (float("nan"), float("inf"), float("-inf")):
        minimal_entry.hamiltonian.metadata = {"x": bad}
        with pytest.raises(ValueError, match="NaN and Infinity"):
            write_entry_json(minimal_entry, out)
    assert out.read_text() == good


def test_written_file_has_normal_permissions(
    minimal_entry: QMatEntry, tmp_path: Path
) -> None:
    """The atomic write must not silently make files owner-only (0600)."""
    reference = tmp_path / "reference.txt"
    reference.write_text("x")
    out = write_entry_json(minimal_entry, tmp_path / "e.json")
    assert (out.stat().st_mode & 0o777) == (reference.stat().st_mode & 0o777)


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlinked_destination_is_written_through(
    minimal_entry: QMatEntry, tmp_path: Path
) -> None:
    target = tmp_path / "real.json"
    target.write_text("{}")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    write_entry_json(minimal_entry, link)
    assert link.is_symlink()
    assert read_entry_json(target) == minimal_entry


def test_write_creates_parent_directories_and_overwrites(
    minimal_entry: QMatEntry, tmp_path: Path
) -> None:
    dest = tmp_path / "a" / "b" / "e.json"
    write_entry_json(minimal_entry, dest)
    minimal_entry.tags = ["second"]
    write_entry_json(minimal_entry, dest)
    assert read_entry_json(dest).tags == ["second"]


# ============================================================ read_entry_json


def _write(tmp_path: Path, data: bytes) -> Path:
    p = tmp_path / "in.json"
    p.write_bytes(data)
    return p


HOSTILE_FILES = {
    "empty file": (b"", "not valid JSON"),
    "invalid utf-8": (b"\xff\xfe\x00bad", "not valid UTF-8"),
    "binary junk": (bytes(range(128, 256)), "not valid"),
    "NaN literal": (b'{"schema_version": "0.1", "reference": NaN}', "NaN is not valid JSON"),
    "Infinity literal": (b'{"schema_version": "0.1", "reference": Infinity}', "Infinity is not valid"),
    # Python versions differ in how deep json.loads can go: either it refuses (nested too
    # deeply) or it parses and the schema rejects the unknown key.  Never another exception.
    "deep arrays": (b"[" * 200_000 + b"]" * 200_000, "(nested too deeply|expected an object)"),
    "deep objects": (b'{"a":' * 20_000 + b"1" + b"}" * 20_000, "(nested too deeply|not valid JSON|unknown field)"),
    "huge integer": (b'{"schema_version":"0.1","hamiltonian":{"num_electrons":' + b"9" * 6000 + b"}}", "(not valid JSON|too large|unknown|missing)"),
    "top-level string": (b'"hello"', "expected an object"),
    "top-level null": (b"null", "expected an object"),
}


@pytest.mark.parametrize("name", list(HOSTILE_FILES))
def test_hostile_files_raise_entry_format_error(tmp_path: Path, name: str) -> None:
    """Found: UnicodeDecodeError, RecursionError and bare ValueError leaked."""
    data, match = HOSTILE_FILES[name]
    with pytest.raises(EntryFormatError, match=match):
        read_entry_json(_write(tmp_path, data))


def test_utf8_bom_is_tolerated(minimal_entry: QMatEntry, tmp_path: Path) -> None:
    text = json.dumps(to_dict(minimal_entry)).encode()
    assert read_entry_json(_write(tmp_path, b"\xef\xbb\xbf" + text)) == minimal_entry


def test_directory_is_an_oserror_not_a_crash(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        read_entry_json(tmp_path)


def test_non_finite_numbers_in_dicts_are_rejected(minimal_entry: QMatEntry) -> None:
    d = to_dict(minimal_entry)
    d["hamiltonian"]["basis"]["cutoff_energy_ev"] = float("nan")
    with pytest.raises(EntryFormatError, match="finite number"):
        entry_from_dict(d)
    d = to_dict(minimal_entry)
    d["hamiltonian"]["metadata"] = {"deep": [{"x": float("inf")}]}
    with pytest.raises(EntryFormatError, match=r"metadata\.deep\[0\]\.x.*Infinity"):
        entry_from_dict(d)
    d = to_dict(minimal_entry)
    d["hamiltonian"]["basis"]["cutoff_energy_ev"] = 10**400  # int too large for a float
    with pytest.raises(EntryFormatError, match="too large"):
        entry_from_dict(d)


def test_very_deep_metadata_does_not_overflow_the_stack(minimal_entry: QMatEntry) -> None:
    d = to_dict(minimal_entry)
    deep: Any = 1
    for _ in range(5000):
        deep = {"k": deep}
    d["hamiltonian"]["metadata"] = deep
    entry_from_dict(d)  # must neither crash nor raise RecursionError


def test_type_hints_are_resolved_once_per_class_not_per_object(
    minimal_entry: QMatEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Found: decoding 200,000 terms took 129 s because hints were re-resolved per object."""
    calls = 0
    real = typing.get_type_hints

    def counting(*a: Any, **k: Any) -> Any:
        nonlocal calls
        calls += 1
        return real(*a, **k)

    d = to_dict(minimal_entry)
    d["hamiltonian"]["terms"] = [to_dict(TermMetadata(name=f"t{i}")) for i in range(3000)]
    _schema_of.cache_clear()
    monkeypatch.setattr(typing, "get_type_hints", counting)
    entry_from_dict(d)
    assert calls <= 12, f"type hints resolved {calls} times for 3000 objects"


def test_decoding_many_objects_is_fast_enough(minimal_entry: QMatEntry) -> None:
    d = to_dict(minimal_entry)
    d["hamiltonian"]["terms"] = [to_dict(TermMetadata(name=f"t{i}")) for i in range(20_000)]
    t = time.perf_counter()
    entry_from_dict(d)
    assert time.perf_counter() - t < 5.0  # was ~13 s before the fix


# ===================================================================== basis


@pytest.mark.parametrize(
    "lattice",
    [
        cubic(float("inf")),
        cubic(float("nan")),
        cubic(-1.0),
        LatticeMetadata(a=5, b=5, c=5, alpha=90, beta=90, gamma=0),
        LatticeMetadata(a=5, b=5, c=5, alpha=90, beta=90, gamma=180),
        LatticeMetadata(a=5, b=5, c=5, alpha=float("nan"), beta=90, gamma=90),
        LatticeMetadata(a=5, b=5, c=5, alpha=-10, beta=90, gamma=90),
    ],
)
def test_invalid_cells_raise_value_error(lattice: LatticeMetadata) -> None:
    """Found: inf raised OverflowError and gamma=0 raised ZeroDivisionError."""
    with pytest.raises(ValueError):
        num_plane_waves_exact(lattice, 100.0)


@pytest.mark.parametrize("ecut", [float("inf"), float("nan"), 0.0, -3.0])
def test_invalid_cutoffs_raise_value_error(ecut: float) -> None:
    with pytest.raises(ValueError):
        num_plane_waves_exact(cubic(5.0), ecut)


@pytest.mark.parametrize("ecut", [1e6, 1e8, 1e12, 1e300])
def test_huge_work_is_refused_immediately_not_run(ecut: float) -> None:
    """Found: ENCUT=1e12 hung the process (unbounded O(L^3) enumeration)."""
    si = LatticeMetadata(a=3.8, b=3.8, c=3.8, alpha=60, beta=60, gamma=60)
    t = time.perf_counter()
    with pytest.raises(ValueError, match="estimate"):
        num_plane_waves_exact(si, ecut)
    assert time.perf_counter() - t < 1.0


def test_overflowing_reach_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="too large"):
        num_plane_waves_exact(cubic(1e300), 1e300, max_candidates=None)


def test_work_limit_is_configurable() -> None:
    lat = cubic(10.0)
    n = num_plane_waves_exact(lat, 100.0)
    with pytest.raises(ValueError, match="max_candidates"):
        num_plane_waves_exact(lat, 100.0, max_candidates=100)
    assert num_plane_waves_exact(lat, 100.0, max_candidates=None) == n
    with pytest.raises(ValueError, match="max_candidates"):
        num_plane_waves_from_ecut(lat, 100.0, max_candidates=100)


def test_realistic_large_cells_stay_within_the_default_limit() -> None:
    # a 55 A cubic cell at 520 eV took ~2.4 s and must remain allowed
    assert DEFAULT_MAX_CANDIDATES >= 9_000_000
    assert num_plane_waves_from_ecut(cubic(5.0), 520.0) == 3407


def test_estimate_works_where_exact_is_refused() -> None:
    si = LatticeMetadata(a=3.8, b=3.8, c=3.8, alpha=60, beta=60, gamma=60)
    assert num_plane_waves_estimate(3.8**3 / 2**0.5, 1e12) > 1e15
    assert num_plane_waves_from_ecut(si, 1e12, method="estimate") > 1e15


# ============================================================= MP converters

GOOD_SITE = {"species": [{"element": "Si", "occu": 1}]}


def doc(**lattice: Any) -> dict[str, Any]:
    lat = dict(a=3.8, b=3.8, c=3.8, alpha=60.0, beta=60.0, gamma=60.0) | lattice
    return {"structure": {"lattice": lat, "sites": [GOOD_SITE]}}


def with_structure(**kw: Any) -> dict[str, Any]:
    d = doc()
    d["structure"].update(kw)
    return d


BAD_STRUCTURE_DOCS = {
    "None": None,
    "list": [],
    "string": "x",
    "structure is a string": {"structure": "x"},
    "sites is None": with_structure(sites=None),
    "sites is a dict": with_structure(sites={}),
    "sites is empty": with_structure(sites=[]),
    "site is None": with_structure(sites=[None]),
    "species is None": with_structure(sites=[{"species": None}]),
    "species is empty": with_structure(sites=[{"species": []}]),
    "species lacks element": with_structure(sites=[{"species": [{"occu": 1}]}]),
    "element is a number": with_structure(sites=[{"species": [{"element": 5}]}]),
    "element is empty": with_structure(sites=[{"species": [{"element": ""}]}]),
    "occu is None": with_structure(sites=[{"species": [{"element": "Si", "occu": None}]}]),
    "occu is a string": with_structure(sites=[{"species": [{"element": "Si", "occu": "x"}]}]),
    "lattice a is None": doc(a=None),
    "lattice a is a string": doc(a="x"),
    "lattice a is a bool": doc(a=True),
    "lattice a is NaN": doc(a=float("nan")),
    "lattice a is inf": doc(a=float("inf")),
    "lattice a is negative": doc(a=-3.8),
    "lattice a is zero": doc(a=0.0),
    "angle is zero": doc(gamma=0.0),
    "angle is 180": doc(gamma=180.0),
    "impossible angles": doc(alpha=170.0, beta=170.0, gamma=170.0),
    "lattice is a list": {"structure": {"lattice": [], "sites": [GOOD_SITE]}},
    "symmetry is a string": {**doc(), "symmetry": "x"},
    "symmetry number is a string": {**doc(), "symmetry": {"number": "227"}},
    "symmetry number out of range": {**doc(), "symmetry": {"number": 999}},
    "symmetry number is a bool": {**doc(), "symmetry": {"number": True}},
    "crystal_system is a number": {**doc(), "symmetry": {"crystal_system": 5}},
    "symbol is a list": {**doc(), "symmetry": {"symbol": ["x"]}},
}


@pytest.mark.parametrize("bad", BAD_STRUCTURE_DOCS.values(), ids=list(BAD_STRUCTURE_DOCS))
def test_malformed_structure_docs_raise_value_error(bad: Any) -> None:
    """Found: 15 shapes leaked TypeError/KeyError/AttributeError; 6 were accepted."""
    with pytest.raises(ValueError):
        structure_from_mp_doc(bad)


class _System(enum.Enum):
    cubic = "Cubic"


class _StrSystem(str, enum.Enum):
    cubic = "Cubic"


@pytest.mark.parametrize("system", ["Cubic", _System.cubic, _StrSystem.cubic])
def test_crystal_system_may_be_a_string_or_an_enum(system: Any) -> None:
    """mp-api can return an Enum; the stricter validation must not reject real data."""
    d = {**doc(), "symmetry": {"number": 227, "symbol": "Fd-3m", "crystal_system": system}}
    s = structure_from_mp_doc(d)
    assert s.lattice.crystal_system == "cubic" and s.lattice.spacegroup_number == 227


def task(**incar_and_params: Any) -> dict[str, Any]:
    t: dict[str, Any] = {"input": {"incar": {"ENCUT": 520.0, "ISPIN": 2}, "parameters": {"NELECT": 8.0}}}
    for key, value in incar_and_params.items():
        section, name = key.split("__")
        t["input"][section][name] = value
    return t


BAD_TASK_DOCS = {
    "None": None,
    "list": [],
    "input is a string": {"input": "x"},
    "incar is a list": {"input": {"incar": [1], "parameters": {"NELECT": 8}}},
    "ENCUT is a string": task(incar__ENCUT="x"),
    "ENCUT is None": task(incar__ENCUT=None),
    "ENCUT is NaN": task(incar__ENCUT=float("nan")),
    "ENCUT is inf": task(incar__ENCUT=float("inf")),
    "ENCUT is negative": task(incar__ENCUT=-5.0),
    "ENCUT is zero": task(incar__ENCUT=0.0),
    "ENCUT is huge": task(incar__ENCUT=1e12),
    "NELECT is None": task(parameters__NELECT=None),
    "NELECT is NaN": task(parameters__NELECT=float("nan")),
    "NELECT is inf": task(parameters__NELECT=float("inf")),
    "NELECT is negative": task(parameters__NELECT=-8.0),
    "NELECT is zero": task(parameters__NELECT=0.0),
    "NELECT is fractional": task(parameters__NELECT=7.5),
    "ISPIN is None": task(incar__ISPIN=None),
    "ISPIN is a string": task(incar__ISPIN="two"),
    "ISPIN is 3": task(incar__ISPIN=3),
}


@pytest.mark.parametrize("bad", BAD_TASK_DOCS.values(), ids=list(BAD_TASK_DOCS))
def test_malformed_task_docs_raise_value_error(bad: Any) -> None:
    structure = structure_from_mp_doc(doc())
    with pytest.raises(ValueError):
        hamiltonian_from_mp_task_doc(bad, structure)


def test_valid_task_doc_still_works_and_spin_flags() -> None:
    structure = structure_from_mp_doc(doc())
    h = hamiltonian_from_mp_task_doc(task(), structure)
    assert (h.num_electrons, h.spin_polarized, h.basis.cutoff_energy_ev) == (8, True, 520.0)
    assert not hamiltonian_from_mp_task_doc(task(incar__ISPIN=1), structure).spin_polarized
    # numeric strings are tolerated
    assert hamiltonian_from_mp_task_doc(task(incar__ENCUT="400"), structure).basis.cutoff_energy_ev == 400.0


@pytest.mark.parametrize("bad", [None, [], "x", 5])
def test_functional_detection_rejects_non_mappings(bad: Any) -> None:
    with pytest.raises(ValueError):
        functional_from_mp_task_doc(bad)
    assert functional_from_mp_task_doc({"input": "x"}) == "PBE"  # odd input shape: default


def test_summary_doc_without_a_structure_is_a_clear_error() -> None:
    class Doc:
        structure = None
        symmetry = None

    class Client:
        class materials:
            class summary:
                @staticmethod
                def search(**kw: Any) -> list[Any]:
                    return [Doc()]

    with pytest.raises(ValueError, match="no structure"):
        mp._summary_doc(Client(), "mp-1", None)


def test_import_error_explains_python_version_and_original_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Found: on 3.10 pip installed a broken mp-api and the message blamed a missing install."""
    import builtins

    real = builtins.__import__

    def fake(name: str, *a: Any, **k: Any) -> Any:
        if name.startswith("mp_api"):
            raise ImportError("cannot import name 'NotRequired' from 'typing'")
        return real(name, *a, **k)

    V = collections.namedtuple("V", "major minor micro releaselevel serial")
    monkeypatch.setattr(builtins, "__import__", fake)
    monkeypatch.setattr(sys, "version_info", V(3, 10, 9, "final", 0))
    with pytest.raises(ImportError) as ei:
        mp._open_client("k", mp.MPAdapterConfig())
    msg = str(ei.value)
    assert "NotRequired" in msg and "Python 3.11 or newer" in msg and "3.10" in msg
    monkeypatch.setattr(sys, "version_info", V(3, 12, 0, "final", 0))
    with pytest.raises(ImportError) as ei:
        mp._open_client("k", mp.MPAdapterConfig())
    assert "3.11" not in str(ei.value) and "qmatbridge[mp]" in str(ei.value)


# =================================================================== packaging


def test_package_ships_the_typing_marker() -> None:
    """Found: downstream mypy saw no types because py.typed was missing."""
    assert (Path(qmatbridge.__file__).parent / "py.typed").exists()
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "Typing :: Typed" in pyproject
    assert re.search(r'qmatbridge\s*=\s*\["py.typed"\]', pyproject)


def test_mp_extra_is_restricted_to_python_311_plus() -> None:
    """Found: on 3.10 the extra installed a stack whose import fails."""
    pyproject = (ROOT / "pyproject.toml").read_text()
    block = pyproject[pyproject.index("\nmp = ["): pyproject.index("\nase = [")]
    assert block.count("python_version >= '3.11'") == 2


def test_ci_matrix_covers_every_supported_python() -> None:
    ci = (ROOT / ".github/workflows/python-package.yml").read_text()
    pyproject = (ROOT / "pyproject.toml").read_text()
    for version in re.findall(r"Programming Language :: Python :: (3\.\d+)", pyproject):
        assert f'"{version}"' in ci, f"{version} is a declared classifier but not in the CI matrix"
