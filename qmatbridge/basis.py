"""Plane-wave basis utilities.

Helpers for relating a kinetic-energy cutoff to the number of plane waves in
a periodic cell.  Pure Python, no required dependencies.

Conventions
-----------
A plane wave ``exp(i G·r)`` is included when its kinetic energy satisfies
``(ħ²/2mₑ)|G|² ≤ Ecut``, with ``ħ²/2mₑ = 3.80998 eV·Å²``.  Counts are
per k-point (Γ-point enumeration for :func:`num_plane_waves_exact`) and
spin-independent.
"""

from __future__ import annotations

import math

from qmatbridge.schema import LatticeMetadata

__all__ = [
    "HBAR2_OVER_2M_EV_A2",
    "cell_volume",
    "cutoff_wavevector",
    "num_plane_waves_estimate",
    "num_plane_waves_exact",
    "num_plane_waves_from_ecut",
]

#: ħ²/2mₑ in eV·Å² (CODATA 2018).
HBAR2_OVER_2M_EV_A2: float = 3.80998212

_Vec = tuple[float, float, float]


def _check_positive(name: str, value: float) -> None:
    if not value > 0:
        raise ValueError(f"{name} must be positive, got {value!r}")


def _lattice_vectors(lat: LatticeMetadata) -> tuple[_Vec, _Vec, _Vec]:
    """Return row vectors a1, a2, a3 (Å) for a standard cell orientation."""
    _check_positive("lattice length a", lat.a)
    _check_positive("lattice length b", lat.b)
    _check_positive("lattice length c", lat.c)
    alpha, beta, gamma = (math.radians(x) for x in (lat.alpha, lat.beta, lat.gamma))
    a1 = (lat.a, 0.0, 0.0)
    a2 = (lat.b * math.cos(gamma), lat.b * math.sin(gamma), 0.0)
    cx = lat.c * math.cos(beta)
    cy = lat.c * (math.cos(alpha) - math.cos(beta) * math.cos(gamma)) / math.sin(gamma)
    cz_sq = lat.c**2 - cx**2 - cy**2
    if cz_sq <= 0:
        raise ValueError("lattice angles do not describe a valid cell")
    return a1, a2, (cx, cy, math.sqrt(cz_sq))


def _cross(u: _Vec, v: _Vec) -> _Vec:
    return (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )


def _dot(u: _Vec, v: _Vec) -> float:
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def cell_volume(lattice: LatticeMetadata) -> float:
    """Unit-cell volume in Å³ from lattice lengths and angles."""
    a1, a2, a3 = _lattice_vectors(lattice)
    return abs(_dot(a1, _cross(a2, a3)))


def cutoff_wavevector(ecut_ev: float) -> float:
    """Cutoff radius ``k_c = sqrt(Ecut / (ħ²/2m))`` in Å⁻¹."""
    _check_positive("ecut_ev", ecut_ev)
    return math.sqrt(ecut_ev / HBAR2_OVER_2M_EV_A2)


def num_plane_waves_estimate(volume_a3: float, ecut_ev: float) -> float:
    """Continuum estimate ``N ≈ V k_c³ / (6π²)`` (real-valued).

    Accurate to a few percent for cells large compared with ``1/k_c``; use
    :func:`num_plane_waves_exact` for small cells.
    """
    _check_positive("volume_a3", volume_a3)
    return volume_a3 * cutoff_wavevector(ecut_ev) ** 3 / (6.0 * math.pi**2)


def num_plane_waves_exact(lattice: LatticeMetadata, ecut_ev: float) -> int:
    """Count reciprocal-lattice vectors G with ``(ħ²/2m)|G|² ≤ Ecut``.

    Enumerates the reciprocal lattice (including the G = 0 term), so the
    result is the Γ-point basis size.
    """
    kc = cutoff_wavevector(ecut_ev)
    a1, a2, a3 = _lattice_vectors(lattice)
    vol = _dot(a1, _cross(a2, a3))
    two_pi = 2.0 * math.pi
    b1, b2, b3 = (
        tuple(two_pi * x / vol for x in _cross(a2, a3)),
        tuple(two_pi * x / vol for x in _cross(a3, a1)),
        tuple(two_pi * x / vol for x in _cross(a1, a2)),
    )
    # G = h b1 + k b2 + l b3 gives G·a_i = 2π (h, k, l)_i, so each Miller
    # index is bounded by |G||a_i| / 2π ≤ kc |a_i| / 2π.
    limits = [
        int(math.floor(kc * math.sqrt(_dot(a, a)) / two_pi)) for a in (a1, a2, a3)
    ]
    kc2 = kc * kc
    count = 0
    for h in range(-limits[0], limits[0] + 1):
        for k in range(-limits[1], limits[1] + 1):
            for l in range(-limits[2], limits[2] + 1):  # noqa: E741
                gx = h * b1[0] + k * b2[0] + l * b3[0]
                gy = h * b1[1] + k * b2[1] + l * b3[1]
                gz = h * b1[2] + k * b2[2] + l * b3[2]
                if gx * gx + gy * gy + gz * gz <= kc2:
                    count += 1
    return count


def num_plane_waves_from_ecut(
    lattice: LatticeMetadata, ecut_ev: float, *, method: str = "exact"
) -> int:
    """Number of plane waves for a cell and cutoff.

    Args:
        lattice:  Cell geometry; lengths in Å, angles in degrees.
        ecut_ev:  Kinetic-energy cutoff in eV.
        method:   ``"exact"`` (reciprocal-lattice enumeration, default) or
                  ``"estimate"`` (continuum formula, rounded to nearest int).
    """
    if method == "exact":
        return num_plane_waves_exact(lattice, ecut_ev)
    if method == "estimate":
        return round(num_plane_waves_estimate(cell_volume(lattice), ecut_ev))
    raise ValueError(f"method must be 'exact' or 'estimate', got {method!r}")
