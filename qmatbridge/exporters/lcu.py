"""Pauli-LCU coefficient exporter for qualtran / pyLIQTR / Cirq.

Writes the plane-wave Hamiltonian of :mod:`qmatbridge.exporters.openfermion_pw`
as a linear combination of unitaries,

.. math::

    H = c_0 \\mathbb{1} + \\sum_{\\ell=1}^{L} \\alpha_\\ell\\, P_\\ell ,
    \\qquad \\lambda = \\sum_\\ell |\\alpha_\\ell| ,

where each ``P_l`` is a Pauli string (Jordan-Wigner, one qubit per spin orbital)
and the ``alpha_l`` are real.  ``lambda`` is the 1-norm that sets the cost of a
qubitization / LCU walk: the identity term is excluded because it only shifts
the energy and is not block-encoded.

This is exactly what the two frameworks consume:

* **PREPARE** loads the normalised magnitudes ``|alpha_l| / lambda``
  (``prepare_probabilities``), for example with qualtran's
  ``StatePreparationAliasSampling.from_probabilities``.
* **SELECT** applies ``sign(alpha_l) P_l`` controlled on the index
  (``pauli_strings`` and ``signs``).  :func:`to_cirq_pauli_sum` builds a
  ``cirq.PauliSum`` from the file, which is how pyLIQTR and Cirq-based tools
  take a Hamiltonian.

The Hamiltonian is the *model* described in the OpenFermion exporter (point
ions with the valence charge, Gamma point, Ewald constant): not the DFT
Hamiltonian of the source calculation.  This is a second-quantized
decomposition; the first-quantized plane-wave oracles of Babbush et al. and
Su et al. use a different, analytic decomposition that this exporter does not
produce.

Conventions
-----------
Character ``i`` of a Pauli string acts on qubit ``i``; qubit ``2 k + s`` is plane
wave ``k`` with spin ``s`` (qubit ``k`` if ``spinless``).  Terms are ordered by
decreasing ``|alpha|`` then lexicographically, so the file is deterministic.
Energies are in Hartree.

Size
----
The number of Pauli terms grows as the fourth power of the number of qubits, so
the exporter refuses more than ``max_plane_waves`` plane waves (default 12).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from qmatbridge.basis import DEFAULT_MAX_CANDIDATES
from qmatbridge.exporters.openfermion_pw import (
    _numpy,
    _openfermion,
    interaction_operator_arrays,
)
from qmatbridge.schema import ExportMetadata, OracleMetadata, QMatEntry, TermMetadata

__all__ = [
    "LCUExporter",
    "lcu_arrays",
    "lcu_oracle_metadata",
    "load_lcu",
    "to_cirq_pauli_sum",
]

_FORMAT = "pauli_lcu_npz"
DEFAULT_MAX_PLANE_WAVES = 12
_PAULI_CHARS = {"X", "Y", "Z"}


def lcu_arrays(
    entry: QMatEntry,
    *,
    ecut_ev: float | None = None,
    spinless: bool = False,
    max_plane_waves: int = DEFAULT_MAX_PLANE_WAVES,
    max_candidates: int | None = DEFAULT_MAX_CANDIDATES,
    threshold: float = 1e-12,
) -> dict[str, Any]:
    """Pauli-LCU decomposition of *entry*'s plane-wave Hamiltonian.

    Returns a dict with ``pauli_strings`` (``(L,)`` unicode), ``coefficients``
    (``(L,)`` float, Ha), ``signs`` (``(L,)`` ±1), ``prepare_probabilities``
    (``(L,)``, sums to 1), the scalars ``identity_coefficient``, ``lambda_total``,
    ``num_qubits``, ``num_terms``, ``num_plane_waves``, ``spinless``,
    ``ecut_ev``, ``truncation_threshold``, ``num_electrons`` and the entry's
    ``canonical_hash``.

    Args:
        threshold: Drop Pauli terms with ``|alpha| <= threshold`` Ha.

    Raises:
        ValueError: As :func:`interaction_operator_arrays`, for a negative
            *threshold*, a decomposition with no non-identity term, or a
            non-Hermitian result (imaginary coefficient above rounding).
    """
    np = _numpy()
    of = _openfermion()
    if not threshold >= 0:
        raise ValueError(f"threshold must be non-negative, got {threshold!r}")
    arrays = interaction_operator_arrays(
        entry,
        ecut_ev=ecut_ev,
        spinless=spinless,
        max_plane_waves=max_plane_waves,
        max_candidates=max_candidates,
    )
    qubit_op = of.jordan_wigner(
        of.InteractionOperator(
            float(arrays["constant"]),
            arrays["one_body_tensor"],
            arrays["two_body_tensor"],
        )
    )
    n_qubits = int(of.count_qubits(qubit_op))

    identity = 0.0
    rows: list[tuple[str, float]] = []
    scale = max((abs(c) for c in qubit_op.terms.values()), default=0.0)
    for term, coeff in qubit_op.terms.items():
        if abs(coeff.imag) > 1e-9 * max(scale, 1.0):
            raise ValueError(
                f"Pauli coefficient {coeff!r} is not real: "
                "the Hamiltonian is not Hermitian"
            )
        if not term:
            identity = float(coeff.real)
            continue
        if abs(coeff.real) <= threshold:
            continue
        chars = ["I"] * n_qubits
        for qubit, pauli in term:
            chars[qubit] = pauli
        rows.append(("".join(chars), float(coeff.real)))
    if not rows:
        raise ValueError("the decomposition has no non-identity Pauli term")
    rows.sort(key=lambda r: (-abs(r[1]), r[0]))

    coeffs = np.array([c for _, c in rows], dtype=float)
    lam = float(np.abs(coeffs).sum())
    return {
        "pauli_strings": np.array([s for s, _ in rows]),
        "coefficients": coeffs,
        "signs": np.where(coeffs < 0, -1, 1).astype(np.int8),
        "prepare_probabilities": np.abs(coeffs) / lam,
        "identity_coefficient": np.array(identity),
        "lambda_total": np.array(lam),
        "num_qubits": np.array(n_qubits),
        "num_terms": np.array(len(rows)),
        "num_plane_waves": arrays["num_plane_waves"],
        "spinless": arrays["spinless"],
        "ecut_ev": arrays["ecut_ev"],
        "truncation_threshold": np.array(float(threshold)),
        "num_electrons": arrays["num_electrons"],
        "canonical_hash": arrays["canonical_hash"],
    }


def lcu_oracle_metadata(
    arrays: dict[str, Any], *, delta_e: float | None = None
) -> OracleMetadata:
    """An :class:`~qmatbridge.schema.OracleMetadata` describing *arrays*.

    Fills the quantities that follow from the decomposition (``lambda_total``,
    ``num_lcu_terms``, state-register width, one ``pauli_lcu`` term block) and
    nothing that needs a circuit-level choice.  ``delta_e`` is passed through if
    given.  The result is returned, not attached: assign it to
    ``entry.hamiltonian.oracle`` if you want it to replace what is there.
    """
    lam = float(arrays["lambda_total"])
    num_terms = int(arrays["num_terms"])
    return OracleMetadata(
        method="lcu",
        lambda_total=lam,
        num_lcu_terms=num_terms,
        delta_e=delta_e,
        num_bits_state=int(arrays["num_qubits"]),
        oracle_type="SELECT_PREPARE",
        index_encoding="binary",
        terms=[
            TermMetadata(
                name="pauli_lcu",
                lambda_one_norm=lam,
                num_lcu_terms=num_terms,
                truncation_threshold=float(arrays["truncation_threshold"]),
                implementation_notes=(
                    "Jordan-Wigner Pauli decomposition of the model plane-wave "
                    "Hamiltonian; identity term excluded from lambda"
                ),
            )
        ],
        complexity={
            "index_register_qubits": max(1, (num_terms - 1).bit_length()),
        },
        metadata={
            "source": "qmatbridge.exporters.lcu",
            "units": "hartree",
            "identity_coefficient": float(arrays["identity_coefficient"]),
        },
    )


def load_lcu(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Read a file written by this exporter back into a dict of arrays."""
    np = _numpy()
    with np.load(os.fspath(path)) as f:
        return {k: f[k] for k in f.files}


def to_cirq_pauli_sum(data: dict[str, Any] | str | os.PathLike[str]) -> Any:
    """A ``cirq.PauliSum`` of the non-identity terms (and the identity as a constant).

    *data* is the dict from :func:`lcu_arrays` / :func:`load_lcu` or a path.
    Qubit ``i`` is ``cirq.LineQubit(i)``.  Needs ``cirq``.
    """
    try:
        import cirq
    except ImportError as exc:  # pragma: no cover - exercised only without cirq
        raise ImportError(
            "to_cirq_pauli_sum needs Cirq: pip install cirq-core"
        ) from exc
    if not isinstance(data, dict):
        data = load_lcu(data)
    qubits = cirq.LineQubit.range(int(data["num_qubits"]))
    paulis = {"X": cirq.X, "Y": cirq.Y, "Z": cirq.Z}
    total = cirq.PauliSum.from_pauli_strings(
        [cirq.PauliString(float(data["identity_coefficient"]))]
    )
    for string, coeff in zip(data["pauli_strings"], data["coefficients"]):
        ops = {
            qubits[i]: paulis[ch]
            for i, ch in enumerate(str(string))
            if ch in _PAULI_CHARS
        }
        total += cirq.PauliString(ops, coefficient=float(coeff))
    return total


class LCUExporter:
    """Registry exporter ``lcu``::

    from qmatbridge.registry import get_exporter

    meta = get_exporter("lcu").export(entry, path="si_lcu.npz", ecut_ev=20.0)
    entry.exports.append(meta)
    """

    name = "lcu"

    def export(self, entry: QMatEntry, **options: Any) -> ExportMetadata:
        """Write the Pauli-LCU decomposition to ``path`` (``.npz``) and describe it.

        Options:
            path:   Output file (required); ``.npz`` is appended if missing.
            ecut_ev, spinless, max_plane_waves, max_candidates, threshold:
                    See :func:`lcu_arrays`.
        """
        path = options.pop("path", None)
        if path is None:
            raise TypeError("lcu needs path='...npz'")
        allowed = {
            "ecut_ev",
            "spinless",
            "max_plane_waves",
            "max_candidates",
            "threshold",
        }
        unknown = set(options) - allowed
        if unknown:
            raise TypeError(
                "unexpected option(s) for lcu: " + ", ".join(sorted(unknown))
            )
        np = _numpy()
        of = _openfermion()
        arrays = lcu_arrays(entry, **options)
        out = os.fspath(path)
        if not out.endswith(".npz"):
            out += ".npz"
        np.savez_compressed(out, **arrays)
        return ExportMetadata(
            framework="lcu",
            format=_FORMAT,
            target_name=f"pauli_lcu_{int(arrays['num_qubits'])}q",
            status="complete",
            version=of.__version__,
            exported_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            artifact_path=out,
            metadata={
                "num_terms": int(arrays["num_terms"]),
                "num_qubits": int(arrays["num_qubits"]),
                "lambda_total": float(arrays["lambda_total"]),
                "identity_coefficient": float(arrays["identity_coefficient"]),
                "ecut_ev": float(arrays["ecut_ev"]),
                "units": "hartree",
                "consumers": ["qualtran", "pyLIQTR", "cirq"],
                "built_with": f"openfermion {of.__version__}",
                "entry_hash": entry.canonical_hash(),
            },
        )
