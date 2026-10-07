"""The raw plane-wave NumPy exporter."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from qmatbridge.basis import HBAR2_OVER_2M_EV_A2, num_plane_waves_exact  # noqa: E402
from qmatbridge.exporters.numpy_planewave import plane_wave_arrays  # noqa: E402
from qmatbridge.io import read_entry_json  # noqa: E402
from qmatbridge.registry import Exporter, get_exporter  # noqa: E402
from qmatbridge.schema import QMatEntry  # noqa: E402


@pytest.fixture
def si() -> QMatEntry:
    e = read_entry_json("benchmarks/fixtures/Si.json")
    e.hamiltonian.valence_charges = {"Si": 4.0}
    return e


def test_registered_exporter_satisfies_protocol() -> None:
    exp = get_exporter("numpy_planewave")
    assert isinstance(exp, Exporter) and exp.name == "numpy_planewave"


def test_count_matches_basis_metadata_and_exact_counter(si: QMatEntry) -> None:
    arr = plane_wave_arrays(si)
    n = arr["g_vectors"].shape[0]
    assert n == si.hamiltonian.basis.num_plane_waves
    assert n == num_plane_waves_exact(si.reference.structure.lattice, 520.0)


def test_geometry_is_consistent(si: QMatEntry) -> None:
    arr = plane_wave_arrays(si)
    a, b = arr["lattice_vectors"], arr["reciprocal_vectors"]
    assert np.allclose(a @ b.T, 2 * math.pi * np.eye(3))
    assert abs(abs(np.linalg.det(a)) - float(arr["volume_ang3"])) < 1e-9
    g, m = arr["g_vectors"], arr["miller_indices"]
    assert np.allclose(m @ b, g)
    e = arr["kinetic_energy_ev"]
    assert np.allclose(e, HBAR2_OVER_2M_EV_A2 * (g**2).sum(axis=1))
    assert (np.diff(e) >= -1e-9).all() and e[-1] <= 520.0 + 1e-9
    assert e[0] == 0.0 and (m[0] == 0).all()  # G = 0 first
    # the set is closed under inversion
    assert {tuple(x) for x in m} == {tuple(-x) for x in m}


def test_structure_factor(si: QMatEntry) -> None:
    arr = plane_wave_arrays(si)
    s = arr["ionic_structure_factor"]
    assert s[0] == pytest.approx(8.0)  # S(0) = total ionic charge
    direct = sum(
        4.0 * np.exp(-1j * arr["g_vectors"] @ r) for r in arr["atom_cart_coords"]
    )
    assert np.allclose(s, direct)
    assert np.abs(s).max() <= 8.0 + 1e-9


def test_export_writes_npz_and_describes_it(si: QMatEntry, tmp_path: Path) -> None:
    meta = get_exporter("numpy_planewave").export(si, path=tmp_path / "si")
    assert meta.status == "complete" and meta.framework == "numpy"
    assert meta.artifact_path == str(tmp_path / "si.npz")
    assert meta.metadata["entry_hash"] == si.canonical_hash()
    with np.load(meta.artifact_path) as z:
        assert z["g_vectors"].shape[0] == meta.metadata["num_plane_waves"]
        assert int(z["num_electrons"]) == 8
        assert str(z["canonical_hash"]) == si.canonical_hash()
        assert list(z["atom_elements"]) == ["Si", "Si"]
    json.dumps(si.to_dict())  # entry untouched and still serialisable
    si.exports.append(meta)


def test_deterministic(si: QMatEntry) -> None:
    a, b = plane_wave_arrays(si), plane_wave_arrays(si)
    assert all(np.array_equal(a[k], b[k]) for k in a)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda e: setattr(e.reference.structure, "sites", []), "no atomic positions"),
        (lambda e: setattr(e.hamiltonian, "valence_charges", {}), "no valence charges"),
        (lambda e: setattr(e.hamiltonian, "valence_charges", {"Si": 5.0}), "sum to 10"),
        (lambda e: setattr(e.hamiltonian, "valence_charges", {"Ge": 4.0}), "Si"),
        (lambda e: setattr(e.hamiltonian.basis, "type", "gaussian"), "plane_wave"),
        (lambda e: setattr(e.hamiltonian.basis, "cutoff_energy_ev", None), "plane_wave"),
    ],
)
def test_refuses_incomplete_entries(si: QMatEntry, mutate, match: str) -> None:  # type: ignore[no-untyped-def]
    mutate(si)
    with pytest.raises(ValueError, match=match):
        plane_wave_arrays(si)


def test_work_limit(si: QMatEntry) -> None:
    with pytest.raises(ValueError, match="max_candidates"):
        plane_wave_arrays(si, max_candidates=10)


def test_option_errors(si: QMatEntry, tmp_path: Path) -> None:
    exp = get_exporter("numpy_planewave")
    with pytest.raises(TypeError, match="path"):
        exp.export(si)
    with pytest.raises(TypeError, match="unexpected"):
        exp.export(si, path=tmp_path / "x", bogus=1)
