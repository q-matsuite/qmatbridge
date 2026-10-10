"""The Pauli-LCU coefficient exporter."""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")
of = pytest.importorskip("openfermion")

from qmatbridge.exporters.lcu import (  # noqa: E402
    lcu_arrays,
    lcu_oracle_metadata,
    load_lcu,
    to_cirq_pauli_sum,
)
from qmatbridge.exporters.openfermion_pw import interaction_operator  # noqa: E402
from qmatbridge.registry import Exporter, get_exporter  # noqa: E402
from qmatbridge.schema import QMatEntry  # noqa: E402
from tests.unit.test_openfermion_export import helium_in_a_box  # noqa: E402

PAULI = {
    "I": np.eye(2),
    "X": np.array([[0, 1], [1, 0]]),
    "Y": np.array([[0, -1j], [1j, 0]]),
    "Z": np.diag([1, -1]),
}


def dense(arrays: dict) -> np.ndarray:
    """Rebuild the matrix from the exported strings; qubit 0 is most significant."""
    n = int(arrays["num_qubits"])
    m = float(arrays["identity_coefficient"]) * np.eye(2**n, dtype=complex)
    for string, c in zip(arrays["pauli_strings"], arrays["coefficients"]):
        op = np.array([[1.0]])
        for ch in str(string):
            op = np.kron(op, PAULI[ch])
        m += c * op
    return m


@pytest.fixture
def he() -> QMatEntry:
    return helium_in_a_box()


def test_decomposition_reproduces_the_fermionic_matrix(he: QMatEntry) -> None:
    # 7 plane waves, one qubit each: small enough to compare full matrices.
    arrays = lcu_arrays(he, ecut_ev=20.0, spinless=True)
    assert int(arrays["num_qubits"]) == 7
    reference = of.get_sparse_operator(
        interaction_operator(he, ecut_ev=20.0, spinless=True)
    ).toarray()
    assert np.allclose(dense(arrays), reference, atol=1e-10)


def test_lambda_bounds_the_spectrum_and_probabilities_are_a_distribution(
    he: QMatEntry,
) -> None:
    arrays = lcu_arrays(he, ecut_ev=20.0, spinless=True)
    lam = float(arrays["lambda_total"])
    assert lam == pytest.approx(np.abs(arrays["coefficients"]).sum())
    shifted = dense(arrays) - float(arrays["identity_coefficient"]) * np.eye(2**7)
    assert np.abs(np.linalg.eigvalsh(shifted)).max() <= lam + 1e-9
    p = arrays["prepare_probabilities"]
    assert p.sum() == pytest.approx(1.0) and (p > 0).all()
    assert np.all(
        arrays["signs"] * np.abs(arrays["coefficients"]) == arrays["coefficients"]
    )


def test_terms_are_ordered_and_deterministic(he: QMatEntry) -> None:
    a = lcu_arrays(he, ecut_ev=20.0, spinless=True)
    b = lcu_arrays(he, ecut_ev=20.0, spinless=True)
    assert list(a["pauli_strings"]) == list(b["pauli_strings"])
    mags = np.abs(a["coefficients"])
    assert (np.diff(mags) <= 1e-15).all()
    assert all(
        set(s) <= set("IXYZ") and "".join(set(s)) != "I" for s in a["pauli_strings"]
    )


def test_threshold_drops_small_terms(he: QMatEntry) -> None:
    full = lcu_arrays(he, ecut_ev=20.0, spinless=True)
    cutoff = float(np.median(np.abs(full["coefficients"])))
    cut = lcu_arrays(he, ecut_ev=20.0, spinless=True, threshold=cutoff)
    assert int(cut["num_terms"]) < int(full["num_terms"])
    assert float(cut["lambda_total"]) <= float(full["lambda_total"])
    with pytest.raises(ValueError, match="threshold"):
        lcu_arrays(he, ecut_ev=20.0, threshold=-1.0)
    with pytest.raises(ValueError, match="no non-identity"):
        lcu_arrays(he, ecut_ev=20.0, spinless=True, threshold=1e9)


def test_refuses_a_large_basis(he: QMatEntry) -> None:
    with pytest.raises(ValueError, match="plane waves"):
        lcu_arrays(he, ecut_ev=200.0, max_plane_waves=12)


def test_spinful_uses_two_qubits_per_plane_wave(he: QMatEntry) -> None:
    arrays = lcu_arrays(he, ecut_ev=20.0)
    assert int(arrays["num_plane_waves"]) == 7 and int(arrays["num_qubits"]) == 14


def test_a_single_plane_wave_has_nothing_to_decompose(he: QMatEntry) -> None:
    # Only G = 0: the q = 0 Coulomb terms are dropped, leaving a constant.
    with pytest.raises(ValueError, match="no non-identity"):
        lcu_arrays(he, ecut_ev=5.0)


def test_cirq_pauli_sum_matches_the_dense_matrix(he: QMatEntry) -> None:
    cirq = pytest.importorskip("cirq")
    arrays = lcu_arrays(he, ecut_ev=20.0, spinless=True)
    ps = to_cirq_pauli_sum(arrays)
    qubits = cirq.LineQubit.range(7)
    assert np.allclose(ps.matrix(qubits), dense(arrays), atol=1e-10)


def test_oracle_metadata_reflects_the_decomposition(he: QMatEntry) -> None:
    arrays = lcu_arrays(he, ecut_ev=20.0, spinless=True)
    oracle = lcu_oracle_metadata(arrays, delta_e=1e-3)
    assert oracle.method == "lcu"
    assert oracle.lambda_total == pytest.approx(float(arrays["lambda_total"]))
    assert oracle.num_lcu_terms == int(arrays["num_terms"])
    assert oracle.num_bits_state == 7
    assert oracle.delta_e == 1e-3
    assert oracle.terms[0].lambda_one_norm == oracle.lambda_total
    assert 2 ** oracle.complexity["index_register_qubits"] >= oracle.num_lcu_terms


def test_exporter_round_trip(he: QMatEntry, tmp_path) -> None:
    exporter = get_exporter("lcu")
    assert isinstance(exporter, Exporter)
    meta = exporter.export(he, path=tmp_path / "he", ecut_ev=20.0, spinless=True)
    assert meta.framework == "lcu" and meta.format == "pauli_lcu_npz"
    assert meta.artifact_path.endswith("he.npz")
    assert meta.metadata["entry_hash"] == he.canonical_hash()
    loaded = load_lcu(meta.artifact_path)
    assert float(loaded["lambda_total"]) == pytest.approx(meta.metadata["lambda_total"])
    assert np.allclose(
        dense(loaded), dense(lcu_arrays(he, ecut_ev=20.0, spinless=True))
    )


def test_exporter_rejects_bad_options(he: QMatEntry, tmp_path) -> None:
    exporter = get_exporter("lcu")
    with pytest.raises(TypeError, match="path"):
        exporter.export(he)
    with pytest.raises(TypeError, match="unexpected"):
        exporter.export(he, path=tmp_path / "x", bogus=1)
