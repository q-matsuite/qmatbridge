"""OpenFermion ``InteractionOperator`` exporter.

Turns an entry into the second-quantized plane-wave Hamiltonian that
OpenFermion works with, in Hartree atomic units.

The model
---------
For plane waves ``phi_G(r) = exp(i G.r) / sqrt(volume)`` at the Gamma point,

.. math::

    H = \\sum_G \\tfrac12 |G|^2 a_G^\\dagger a_G
        + \\sum_{G,G'} V(G-G')\\, a_G^\\dagger a_{G'}
        + \\tfrac12 \\sum_{G_1,G_2,q\\ne0} \\frac{4\\pi}{\\Omega q^2}
          a_{G_1+q}^\\dagger a_{G_2-q}^\\dagger a_{G_2} a_{G_1}
        + E_\\text{Ewald}

with ``V(q) = -(4 pi / (Omega q^2)) sum_a Z_a exp(-i q.R_a)`` for ``q != 0``.

**This is a model, not the DFT Hamiltonian.** The ions are point charges whose
strength is the entry's per-species valence charge ``Z_a``; no pseudopotential
form factor is available from the entry, so none is applied.  The ``q = 0``
terms of the three Coulomb interactions cancel for a neutral cell (the exporter
requires the valence charges to sum to ``num_electrons``) and are dropped; the
constant is the Ewald energy of the point ions in their neutralising background.
The basis is truncated to the plane waves with kinetic energy up to ``ecut_ev``
and the interaction is restricted to that set.

Size
----
The two-body tensor has ``(2N)^4`` entries for ``N`` plane waves (``N^4`` with
``spinless=True``), so only small bases are practical.  The exporter refuses
more than ``max_plane_waves`` (default 32) rather than allocate gigabytes;
lower ``ecut_ev`` to select fewer plane waves.  Spin orbital ``2 i + s`` is
plane wave ``i`` with spin ``s`` (OpenFermion's convention for spinful
Hamiltonians).

File format
-----------
``numpy.savez_compressed`` with ``constant``, ``one_body_tensor``,
``two_body_tensor`` (complex), the selected ``g_vectors`` (bohr^-1) and
``miller_indices``, and the scalars ``num_electrons``, ``num_plane_waves``,
``spinless``, ``ecut_ev`` and ``canonical_hash``.  :func:`load_interaction_operator`
rebuilds the OpenFermion object.  (OpenFermion's own ``save_operator`` does not
support ``InteractionOperator``.)
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any

from qmatbridge.basis import DEFAULT_MAX_CANDIDATES, cell_volume
from qmatbridge.exporters.numpy_planewave import plane_wave_arrays
from qmatbridge.schema import ExportMetadata, QMatEntry

__all__ = [
    "BOHR_ANGSTROM",
    "HARTREE_EV",
    "OpenFermionExporter",
    "ewald_energy",
    "interaction_operator",
    "interaction_operator_arrays",
    "load_interaction_operator",
]

#: CODATA 2018 values.
BOHR_ANGSTROM = 0.529177210903
HARTREE_EV = 27.211386245988

_FORMAT = "interaction_operator_npz"
DEFAULT_MAX_PLANE_WAVES = 32


def _numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - exercised only without numpy
        raise ImportError(
            "the openfermion exporter needs NumPy: pip install qmatbridge[openfermion]"
        ) from exc
    return np


def _openfermion() -> Any:
    try:
        import openfermion
    except ImportError as exc:
        raise ImportError(
            "the openfermion exporter needs OpenFermion: "
            "pip install qmatbridge[openfermion]"
        ) from exc
    return openfermion


# ---------------------------------------------------------------------------
# Ewald energy of point ions in a neutralising background
# ---------------------------------------------------------------------------


def ewald_energy(
    lattice: Any, positions: Any, charges: Any, *, eta: float | None = None
) -> float:
    """Ewald energy (Hartree) of point charges in a uniform neutralising background.

    Args:
        lattice:   ``(3, 3)`` rows a1, a2, a3 in bohr.
        positions: ``(A, 3)`` Cartesian positions in bohr.
        charges:   ``(A,)`` positive charges.
        eta:       Splitting parameter in bohr^-1.  The result does not depend on
                   it; the default balances the real- and reciprocal-space sums.
                   Exposed so tests can check that independence.

    Returns:
        ``E = 1/2 sum' Z_a Z_b erfc(eta r)/r + (2 pi / Omega) sum_{G!=0}
        |S(G)|^2 exp(-G^2 / 4 eta^2) / G^2 - (eta/sqrt(pi)) sum Z_a^2
        - pi (sum Z_a)^2 / (2 Omega eta^2)``.
    """
    np = _numpy()
    a = np.asarray(lattice, dtype=float)
    pos = np.asarray(positions, dtype=float)
    z = np.asarray(charges, dtype=float)
    omega = abs(float(np.linalg.det(a)))
    b = 2.0 * math.pi * np.linalg.inv(a).T
    if eta is None:
        eta = math.sqrt(math.pi) / omega ** (1.0 / 3.0)
    t = 6.0  # erfc(6) ~ 2e-17: both sums are converged to double precision
    r_cut, g_cut = t / eta, 2.0 * eta * t

    def reach(vectors: Any, cutoff: float, per: float) -> list[int]:
        # Integer range along each axis that covers a sphere of radius *cutoff*.
        return [int(math.ceil(cutoff * np.linalg.norm(v) / per)) + 1 for v in vectors]

    def grid(n: list[int]) -> Any:
        axes = [np.arange(-k, k + 1) for k in n]
        return np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)

    # Real space.
    shifts = grid(reach(b, r_cut, 2.0 * math.pi)) @ a
    d = pos[:, None, None, :] - pos[None, :, None, :] + shifts[None, None, :, :]
    r = np.linalg.norm(d, axis=-1)
    zz = z[:, None, None] * z[None, :, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(r < 1e-12, 0.0, zz * _erfc(eta * r) / r)
    e_real = 0.5 * float(term[r <= r_cut].sum())

    # Reciprocal space.
    gv = grid(reach(a, g_cut, 2.0 * math.pi)) @ b
    g2 = np.einsum("ij,ij->i", gv, gv)
    keep = (g2 > 1e-12) & (g2 <= g_cut * g_cut)
    gv, g2 = gv[keep], g2[keep]
    s = (z[None, :] * np.exp(-1j * (gv @ pos.T))).sum(axis=1)
    e_recip = (2.0 * math.pi / omega) * float(
        (np.abs(s) ** 2 * np.exp(-g2 / (4.0 * eta * eta)) / g2).sum()
    )

    e_self = -eta / math.sqrt(math.pi) * float((z * z).sum())
    e_background = -math.pi * float(z.sum()) ** 2 / (2.0 * omega * eta * eta)
    return e_real + e_recip + e_self + e_background


def _erfc(x: Any) -> Any:
    np = _numpy()
    return np.vectorize(math.erfc, otypes=[float])(x)


# ---------------------------------------------------------------------------
# Hamiltonian arrays
# ---------------------------------------------------------------------------


def interaction_operator_arrays(
    entry: QMatEntry,
    *,
    ecut_ev: float | None = None,
    spinless: bool = False,
    max_plane_waves: int = DEFAULT_MAX_PLANE_WAVES,
    max_candidates: int | None = DEFAULT_MAX_CANDIDATES,
) -> dict[str, Any]:
    """Build the constant and the one- and two-body tensors for *entry*.

    Args:
        entry:           Needs positions and valence charges consistent with
                         ``num_electrons`` (see :func:`plane_wave_arrays`).
        ecut_ev:         Keep plane waves with kinetic energy up to this value
                         (default and maximum: the entry's cutoff).
        spinless:        One orbital per plane wave instead of two spin orbitals.
        max_plane_waves: Refuse a larger basis; the two-body tensor grows as
                         the fourth power of the orbital count.

    Raises:
        ValueError: On a bad option, an entry the numpy exporter would refuse, or
            a basis larger than *max_plane_waves*.
    """
    np = _numpy()
    base = plane_wave_arrays(entry, max_candidates=max_candidates)
    entry_ecut = float(base["cutoff_energy_ev"])
    ecut = entry_ecut if ecut_ev is None else float(ecut_ev)
    if not math.isfinite(ecut) or ecut <= 0 or ecut > entry_ecut + 1e-9:
        raise ValueError(
            f"ecut_ev must be in (0, {entry_ecut:g}] (the entry's cutoff), "
            f"got {ecut_ev!r}"
        )
    if max_plane_waves < 1:
        raise ValueError("max_plane_waves must be at least 1")
    keep = base["kinetic_energy_ev"] <= ecut + 1e-9
    n = int(keep.sum())
    if n == 0:
        raise ValueError(f"no plane wave has kinetic energy <= {ecut:g} eV")
    if n > max_plane_waves:
        raise ValueError(
            f"ecut_ev={ecut:g} eV selects {n} plane waves, more than "
            f"max_plane_waves={max_plane_waves}: the two-body tensor would have "
            f"{(n if spinless else 2 * n) ** 4:,} entries. Lower ecut_ev or raise "
            "max_plane_waves."
        )

    to_bohr = 1.0 / BOHR_ANGSTROM
    miller = base["miller_indices"][keep]
    g = base["g_vectors"][keep] * BOHR_ANGSTROM  # 1/bohr
    a = base["lattice_vectors"] * to_bohr
    pos = base["atom_cart_coords"] * to_bohr
    z = base["atom_charges"]
    omega = cell_volume(entry.reference.structure.lattice) * to_bohr**3

    # One-body: kinetic + point-ion potential, V(G - G') for G != G'.
    dg = g[:, None, :] - g[None, :, :]  # (n, n, 3): G_i - G_j
    q2 = np.einsum("ijk,ijk->ij", dg, dg)
    off = q2 > 1e-12
    phase = np.exp(-1j * np.einsum("ijk,ak->ija", dg, pos))  # (n, n, A)
    s_q = np.einsum("ija,a->ij", phase, z)
    h = np.zeros((n, n), dtype=complex)
    h[off] = -4.0 * math.pi / omega * s_q[off] / q2[off]
    h[np.diag_indices(n)] += 0.5 * np.einsum("ij,ij->i", g, g)

    # Two-body: (1/2) sum v(q) a+_{G1+q} a+_{G2-q} a_{G2} a_{G1}, keeping only
    # the terms whose four plane waves are all in the basis.
    index = {tuple(m): i for i, m in enumerate(miller.tolist())}
    # spatial[p, q, r, s] multiplies a+_p a+_q a_r a_s with p=G1+q, q=G2-q, r=G2, s=G1.
    spatial = np.zeros((n, n, n, n), dtype=float)
    for s_idx in range(n):
        for r_idx in range(n):
            for p_idx in range(n):
                if p_idx == s_idx:
                    continue  # q = 0
                q_idx = index.get(
                    tuple((miller[r_idx] - miller[p_idx] + miller[s_idx]).tolist())
                )
                if q_idx is None:
                    continue
                qv = g[p_idx] - g[s_idx]
                spatial[p_idx, q_idx, r_idx, s_idx] = (
                    0.5 * 4.0 * math.pi / (omega * float(qv @ qv))
                )

    if spinless:
        one_body, two_body = h, spatial.astype(complex)
    else:
        m = 2 * n
        one_body = np.zeros((m, m), dtype=complex)
        two_body = np.zeros((m, m, m, m), dtype=complex)
        for s1 in (0, 1):
            one_body[s1::2, s1::2] = h
            for s2 in (0, 1):
                two_body[s1::2, s2::2, s2::2, s1::2] = spatial

    return {
        "constant": np.array(ewald_energy(a, pos, z)),
        "one_body_tensor": one_body,
        "two_body_tensor": two_body,
        "g_vectors": g,
        "miller_indices": miller,
        "num_electrons": base["num_electrons"],
        "num_plane_waves": np.array(n),
        "spinless": np.array(spinless),
        "ecut_ev": np.array(ecut),
        "canonical_hash": base["canonical_hash"],
    }


def interaction_operator(entry: QMatEntry, **options: Any) -> Any:
    """Return the entry's ``openfermion.InteractionOperator``.

    Accepts the options of :func:`interaction_operator_arrays`.
    """
    of = _openfermion()
    arrays = interaction_operator_arrays(entry, **options)
    return of.InteractionOperator(
        float(arrays["constant"]), arrays["one_body_tensor"], arrays["two_body_tensor"]
    )


def load_interaction_operator(path: str | os.PathLike[str]) -> Any:
    """Rebuild the ``InteractionOperator`` from a file this exporter wrote."""
    np = _numpy()
    of = _openfermion()
    with np.load(os.fspath(path)) as f:
        return of.InteractionOperator(
            float(f["constant"]), f["one_body_tensor"], f["two_body_tensor"]
        )


class OpenFermionExporter:
    """Registry exporter ``openfermion``::

        from qmatbridge.registry import get_exporter

        meta = get_exporter("openfermion").export(
            entry, path="si.npz", ecut_ev=40.0
        )
        entry.exports.append(meta)
    """

    name = "openfermion"

    def export(self, entry: QMatEntry, **options: Any) -> ExportMetadata:
        """Write *entry*'s Hamiltonian to ``path`` (``.npz``) and describe it.

        Options:
            path:            Output file (required); ``.npz`` is appended if missing.
            ecut_ev, spinless, max_plane_waves, max_candidates:
                             See :func:`interaction_operator_arrays`.
        """
        path = options.pop("path", None)
        if path is None:
            raise TypeError("openfermion needs path='...npz'")
        allowed = {"ecut_ev", "spinless", "max_plane_waves", "max_candidates"}
        unknown = set(options) - allowed
        if unknown:
            raise TypeError(
                "unexpected option(s) for openfermion: " + ", ".join(sorted(unknown))
            )
        np = _numpy()
        of = _openfermion()
        arrays = interaction_operator_arrays(entry, **options)
        out = os.fspath(path)
        if not out.endswith(".npz"):
            out += ".npz"
        np.savez_compressed(out, **arrays)
        n = int(arrays["num_plane_waves"])
        spin_orbitals = n if bool(arrays["spinless"]) else 2 * n
        return ExportMetadata(
            framework="openfermion",
            format=_FORMAT,
            target_name=f"openfermion_pw_{spin_orbitals}so",
            status="complete",
            version=of.__version__,
            exported_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            artifact_path=out,
            metadata={
                "num_plane_waves": n,
                "num_spin_orbitals": spin_orbitals,
                "ecut_ev": float(arrays["ecut_ev"]),
                "units": "hartree",
                "model": (
                    "point-charge ions (Z = valence charge), Gamma point, "
                    "q=0 terms dropped for a neutral cell, Ewald constant"
                ),
                "entry_hash": entry.canonical_hash(),
            },
        )
