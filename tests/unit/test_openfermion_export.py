"""The OpenFermion InteractionOperator exporter."""

from __future__ import annotations

import math

import pytest

np = pytest.importorskip("numpy")

from qmatbridge.exporters.openfermion_pw import (  # noqa: E402
    BOHR_ANGSTROM,
    HARTREE_EV,
    ewald_energy,
    interaction_operator_arrays,
)
from qmatbridge.io import read_entry_json  # noqa: E402
from qmatbridge.registry import Exporter, get_exporter  # noqa: E402
from qmatbridge.schema import QMatEntry, SiteMetadata  # noqa: E402


@pytest.fixture
def si() -> QMatEntry:
    e = read_entry_json("benchmarks/fixtures/Si.json")
    e.hamiltonian.valence_charges = {"Si": 4.0}
    return e


def helium_in_a_box(box_bohr: float = 6.0) -> QMatEntry:
    """One He ion (Z=2) and two electrons in a cubic box, 20 eV basis."""
    e = read_entry_json("benchmarks/fixtures/Si.json")
    s, lat = e.reference.structure, e.reference.structure.lattice
    lat.a = lat.b = lat.c = box_bohr * BOHR_ANGSTROM
    lat.alpha = lat.beta = lat.gamma = 90.0
    lat.volume_ang3 = None
    s.sites = [SiteMetadata(element="He", frac_coords=(0.1, 0.2, 0.3))]
    s.species, s.num_sites = ["He"], 1
    s.formula_reduced = s.formula_unit_cell = "He"
    e.hamiltonian.num_electrons = 2
    e.hamiltonian.valence_charges = {"He": 2.0}
    return e


# --- Ewald energy -----------------------------------------------------------


@pytest.mark.parametrize("a", [1.0, 7.3])
def test_ewald_reproduces_the_simple_cubic_wigner_crystal(a: float) -> None:
    # E = -0.880059 / r_s per ion for a simple-cubic lattice in its background.
    r_s = (3 * a**3 / (4 * math.pi)) ** (1 / 3)
    e = ewald_energy(np.eye(3) * a, [[0.0, 0.0, 0.0]], [1.0])
    assert e * r_s == pytest.approx(-0.880059442, abs=1e-8)


def test_ewald_does_not_depend_on_the_splitting_parameter() -> None:
    a = 10.2 * np.array([[0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]])
    pos = np.array([[0.0, 0, 0], [2.55, 2.55, 2.55]])
    values = [ewald_energy(a, pos, [4.0, 4.0], eta=eta) for eta in (0.25, 0.4, 0.7)]
    assert max(values) - min(values) < 1e-9


# --- Hamiltonian arrays -----------------------------------------------------


def test_arrays_shapes_and_hermiticity(si: QMatEntry) -> None:
    arr = interaction_operator_arrays(si, ecut_ev=30.0)
    n = int(arr["num_plane_waves"])
    assert 1 < n <= 32
    h, t = arr["one_body_tensor"], arr["two_body_tensor"]
    assert h.shape == (2 * n, 2 * n) and t.shape == (2 * n,) * 4
    assert np.allclose(h, h.conj().T)
    assert np.allclose(t, np.einsum("pqrs->srqp", t).conj())
    # spin: no one-body coupling between up (even) and down (odd) orbitals
    assert not h[0::2, 1::2].any()
    assert np.allclose(h[0::2, 0::2], h[1::2, 1::2])
    assert float(arr["constant"]) == pytest.approx(-8.378, abs=0.01)


def test_kinetic_energy_is_in_hartree(si: QMatEntry) -> None:
    arr = interaction_operator_arrays(si, ecut_ev=30.0, spinless=True)
    g = arr["g_vectors"]
    # compare with the numpy exporter's eV values through the unit constant
    from qmatbridge.exporters.numpy_planewave import plane_wave_arrays

    base = plane_wave_arrays(si)
    n = g.shape[0]
    assert np.allclose(
        0.5 * (g**2).sum(axis=1), base["kinetic_energy_ev"][:n] / HARTREE_EV
    )


def test_spinless_has_half_the_orbitals(si: QMatEntry) -> None:
    arr = interaction_operator_arrays(si, ecut_ev=30.0, spinless=True)
    n = int(arr["num_plane_waves"])
    assert arr["one_body_tensor"].shape == (n, n)


@pytest.mark.parametrize("bad", [0.0, -1.0, 600.0, float("nan")])
def test_ecut_must_be_within_the_entry_cutoff(si: QMatEntry, bad: float) -> None:
    with pytest.raises(ValueError, match="ecut_ev"):
        interaction_operator_arrays(si, ecut_ev=bad)


def test_refuses_a_basis_that_would_be_too_large(si: QMatEntry) -> None:
    with pytest.raises(ValueError, match=r"max_plane_waves=32.*entries"):
        interaction_operator_arrays(si)  # the full 520 eV basis
    with pytest.raises(ValueError, match="max_plane_waves"):
        interaction_operator_arrays(si, ecut_ev=30.0, max_plane_waves=5)


def test_refuses_what_the_numpy_exporter_refuses(si: QMatEntry) -> None:
    si.hamiltonian.valence_charges = {}
    with pytest.raises(ValueError, match="valence charges"):
        interaction_operator_arrays(si, ecut_ev=30.0)


# --- OpenFermion ------------------------------------------------------------


def test_agrees_with_openfermions_own_plane_wave_hamiltonian() -> None:
    of = pytest.importorskip("openfermion")
    from openfermion.hamiltonians import plane_wave_hamiltonian
    from openfermion.utils import Grid

    box = 6.0
    entry = helium_in_a_box(box)
    arr = interaction_operator_arrays(
        entry, ecut_ev=20.0, spinless=True, max_plane_waves=64
    )
    miller = arr["miller_indices"].tolist()
    n = len(miller)

    grid = Grid(dimensions=3, length=5, scale=box)  # momentum transfers up to 2 do not alias
    reference = plane_wave_hamiltonian(
        grid,
        [("He", (0.6, 1.2, 1.8))],
        spinless=True,
        plane_wave=True,
        e_cutoff=0.6,  # Hartree: the |m| <= 1 shells, as in our 20 eV basis
    )
    # OpenFermion's plane waves are exp(-i k.r), ours exp(+i G.r): mode k <-> G = -k.
    index = [
        grid.orbital_id(tuple(grid.momentum_ints_to_index([-x for x in m])), None)
        for m in miller
    ]
    ours = of.normal_ordered(
        of.get_fermion_operator(
            of.InteractionOperator(
                0.0, arr["one_body_tensor"], arr["two_body_tensor"]
            )
        )
    )
    mine, theirs = of.FermionOperator(), of.FermionOperator()
    for term, c in ours.terms.items():
        if term:
            mine += of.FermionOperator(tuple((index[i], d) for i, d in term), c)
    inside = set(index)
    for term, c in of.normal_ordered(reference).terms.items():
        if term and all(i in inside for i, _ in term):
            theirs += of.FermionOperator(term, c)
    assert len(mine.terms) == len(theirs.terms) > n
    diff = of.normal_ordered(mine - theirs)
    assert max((abs(c) for c in diff.terms.values()), default=0.0) < 1e-10


def test_exporter_roundtrip_and_registry(si: QMatEntry, tmp_path) -> None:
    of = pytest.importorskip("openfermion")
    from qmatbridge.exporters.openfermion_pw import (
        interaction_operator,
        load_interaction_operator,
    )

    exporter = get_exporter("openfermion")
    assert isinstance(exporter, Exporter) and exporter.name == "openfermion"
    meta = exporter.export(si, path=tmp_path / "si", ecut_ev=30.0)
    assert meta.framework == "openfermion" and meta.format == "interaction_operator_npz"
    assert meta.artifact_path.endswith("si.npz")
    assert meta.metadata["entry_hash"] == si.canonical_hash()
    assert meta.metadata["num_spin_orbitals"] == 2 * meta.metadata["num_plane_waves"]
    assert meta.version == of.__version__

    loaded = load_interaction_operator(meta.artifact_path)
    direct = interaction_operator(si, ecut_ev=30.0)
    assert isinstance(loaded, of.InteractionOperator)
    assert loaded.constant == pytest.approx(direct.constant)
    assert np.allclose(loaded.one_body_tensor, direct.one_body_tensor)
    assert np.allclose(loaded.two_body_tensor, direct.two_body_tensor)
    assert of.is_hermitian(of.get_fermion_operator(loaded))


def test_exporter_option_errors(si: QMatEntry, tmp_path) -> None:
    pytest.importorskip("openfermion")
    exporter = get_exporter("openfermion")
    with pytest.raises(TypeError, match="path"):
        exporter.export(si)
    with pytest.raises(TypeError, match="unexpected"):
        exporter.export(si, path=tmp_path / "x", bogus=1)
