"""Tests for qmatbridge.basis."""

from __future__ import annotations

import math

import pytest

from qmatbridge.basis import (
    HBAR2_OVER_2M_EV_A2,
    cell_volume,
    cutoff_wavevector,
    num_plane_waves_estimate,
    num_plane_waves_exact,
    num_plane_waves_from_ecut,
)
from qmatbridge.schema import LatticeMetadata


def cubic(a: float) -> LatticeMetadata:
    return LatticeMetadata(a=a, b=a, c=a, alpha=90.0, beta=90.0, gamma=90.0)


def si_primitive() -> LatticeMetadata:
    return LatticeMetadata(
        a=3.867, b=3.867, c=3.867, alpha=60.0, beta=60.0, gamma=60.0
    )


def test_cell_volume_cubic() -> None:
    assert cell_volume(cubic(4.0)) == pytest.approx(64.0)


def test_cell_volume_fcc_primitive_is_quarter_conventional() -> None:
    # fcc primitive (60° rhombohedral, a = a_conv/√2) has V = a_conv³ / 4.
    a_conv = 5.468
    lat = LatticeMetadata(
        a=a_conv / math.sqrt(2),
        b=a_conv / math.sqrt(2),
        c=a_conv / math.sqrt(2),
        alpha=60.0,
        beta=60.0,
        gamma=60.0,
    )
    assert cell_volume(lat) == pytest.approx(a_conv**3 / 4, rel=1e-9)


def test_cutoff_wavevector() -> None:
    assert cutoff_wavevector(HBAR2_OVER_2M_EV_A2) == pytest.approx(1.0)


def test_exact_counts_origin_only_below_first_shell() -> None:
    # First nonzero |G| = 2π/a; just below that cutoff only G = 0 remains.
    a = 10.0
    e_first = HBAR2_OVER_2M_EV_A2 * (2 * math.pi / a) ** 2
    assert num_plane_waves_exact(cubic(a), 0.99 * e_first) == 1
    # Including the shell adds the 6 nearest neighbours.
    assert num_plane_waves_exact(cubic(a), 1.01 * e_first) == 7


def test_exact_matches_estimate_for_large_cell() -> None:
    lat = cubic(20.0)
    exact = num_plane_waves_exact(lat, 200.0)
    est = num_plane_waves_estimate(cell_volume(lat), 200.0)
    assert exact == pytest.approx(est, rel=0.02)


def test_silicon_primitive_cell_order_of_magnitude() -> None:
    n = num_plane_waves_from_ecut(si_primitive(), 520.0)
    assert 1000 < n < 1250
    est = num_plane_waves_from_ecut(si_primitive(), 520.0, method="estimate")
    assert n == pytest.approx(est, rel=0.05)


def test_monotonic_in_cutoff() -> None:
    lat = si_primitive()
    counts = [num_plane_waves_exact(lat, e) for e in (100.0, 200.0, 400.0)]
    assert counts == sorted(counts) and len(set(counts)) == 3


def test_triclinic_matches_estimate() -> None:
    lat = LatticeMetadata(a=9.0, b=10.0, c=11.0, alpha=80.0, beta=95.0, gamma=70.0)
    exact = num_plane_waves_exact(lat, 150.0)
    est = num_plane_waves_estimate(cell_volume(lat), 150.0)
    assert exact == pytest.approx(est, rel=0.05)


@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_rejects_nonpositive_cutoff(bad: float) -> None:
    with pytest.raises(ValueError):
        num_plane_waves_exact(cubic(5.0), bad)


def test_rejects_placeholder_lattice() -> None:
    placeholder = LatticeMetadata(a=0, b=0, c=0, alpha=0, beta=0, gamma=0)
    with pytest.raises(ValueError):
        num_plane_waves_from_ecut(placeholder, 500.0)


def test_rejects_invalid_angles() -> None:
    lat = LatticeMetadata(a=3, b=3, c=3, alpha=170.0, beta=170.0, gamma=170.0)
    with pytest.raises(ValueError):
        cell_volume(lat)


def test_unknown_method() -> None:
    with pytest.raises(ValueError):
        num_plane_waves_from_ecut(cubic(5.0), 100.0, method="magic")
