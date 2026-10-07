"""Raw plane-wave arrays exporter (NumPy ``.npz``).

Writes everything a first-quantized plane-wave Hamiltonian is built from, and
nothing derived beyond the ionic structure factor, so that a downstream
compiler or resource estimator can assemble the Hamiltonian its own way:

========================  ==========  =========================================
array                     shape       meaning
========================  ==========  =========================================
``lattice_vectors``       (3, 3)      rows a1, a2, a3 in Å (standard orientation)
``reciprocal_vectors``    (3, 3)      rows b1, b2, b3 in Å⁻¹ (include the 2π)
``miller_indices``        (N, 3)      integer (h, k, l) of each plane wave
``g_vectors``             (N, 3)      G = h b1 + k b2 + l b3 in Å⁻¹
``kinetic_energy_ev``     (N,)        (ħ²/2m)|G|², ascending
``atom_elements``         (A,)        element symbol per atom
``atom_frac_coords``      (A, 3)      fractional positions
``atom_cart_coords``      (A, 3)      Cartesian positions in Å
``atom_charges``          (A,)        valence charge Z_a of each ion
``ionic_structure_factor`` (N,)       S(G) = Σ_a Z_a exp(-i G·R_a)
``scalars``               ()          see below
========================  ==========  =========================================

Plane waves are ``exp(i G·r)`` with ``(ħ²/2m)|G|² ≤ Ecut`` (Γ point), ordered
by kinetic energy then Miller index, so the set matches
``BasisMetadata.num_plane_waves`` exactly.  The ``.npz`` also holds
``num_electrons``, ``spin_polarized``, ``cutoff_energy_ev``, ``volume_ang3`` and
``canonical_hash`` as 0-d arrays.

An entry must carry atomic positions and valence charges that sum to its
electron count (schema 0.3); anything less is refused rather than padded.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any

from qmatbridge.basis import (
    DEFAULT_MAX_CANDIDATES,
    _lattice_vectors,
    cell_volume,
    cutoff_wavevector,
)
from qmatbridge.schema import ExportMetadata, QMatEntry

__all__ = ["NumpyPlaneWaveExporter", "plane_wave_arrays"]

_FORMAT = "plane_wave_npz"


def _numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - exercised only without numpy
        raise ImportError(
            "the numpy_planewave exporter needs NumPy: pip install qmatbridge[numpy]"
        ) from exc
    return np


def plane_wave_arrays(
    entry: QMatEntry, *, max_candidates: int | None = DEFAULT_MAX_CANDIDATES
) -> dict[str, Any]:
    """Build the arrays described in the module docstring for *entry*.

    Raises:
        ValueError: If the entry is not a plane-wave entry with a cutoff, has no
            atomic positions, has no valence charges, the charges disagree with
            ``num_electrons``, or the basis would need more than
            *max_candidates* reciprocal-lattice vectors to enumerate.
    """
    np = _numpy()
    ham, struct = entry.hamiltonian, entry.reference.structure
    if ham.basis.type != "plane_wave" or ham.basis.cutoff_energy_ev is None:
        raise ValueError("entry needs a plane_wave basis with cutoff_energy_ev")
    if not struct.sites:
        raise ValueError("entry has no atomic positions (structure.sites is empty)")
    if not ham.valence_charges:
        raise ValueError(
            "entry has no valence charges (hamiltonian.valence_charges is empty)"
        )
    try:
        entry.check_electron_count()
    except KeyError as exc:
        raise ValueError(str(exc.args[0])) from None

    ecut = ham.basis.cutoff_energy_ev
    kc = cutoff_wavevector(ecut)
    a = np.array(_lattice_vectors(struct.lattice), dtype=float)
    volume = cell_volume(struct.lattice)
    b = 2.0 * math.pi * np.linalg.inv(a).T  # rows b_i with a_i . b_j = 2 pi delta_ij

    lengths = np.linalg.norm(a, axis=1)
    reach = [int(math.floor(kc * float(n) / (2.0 * math.pi))) for n in lengths]
    candidates = math.prod(2 * r + 1 for r in reach)
    if max_candidates is not None and candidates > max_candidates:
        raise ValueError(
            f"enumerating plane waves would test about {candidates:,} vectors "
            f"(limit {max_candidates:,}); pass a larger max_candidates"
        )
    axes = [np.arange(-r, r + 1) for r in reach]
    miller = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    g = miller @ b
    g2 = np.einsum("ij,ij->i", g, g)
    keep = g2 <= kc * kc
    miller, g, g2 = miller[keep], g[keep], g2[keep]
    order = np.lexsort((miller[:, 2], miller[:, 1], miller[:, 0], np.round(g2, 9)))
    miller, g, g2 = miller[order], g[order], g2[order]

    frac = np.array([s.frac_coords for s in struct.sites], dtype=float)
    cart = frac @ a
    charges = np.array(
        [ham.valence_charges[s.element] for s in struct.sites], dtype=float
    )
    structure_factor = (charges[None, :] * np.exp(-1j * (g @ cart.T))).sum(axis=1)

    return {
        "lattice_vectors": a,
        "reciprocal_vectors": b,
        "miller_indices": miller.astype(np.int64),
        "g_vectors": g,
        "kinetic_energy_ev": ecut * g2 / (kc * kc),
        "atom_elements": np.array([s.element for s in struct.sites]),
        "atom_frac_coords": frac,
        "atom_cart_coords": cart,
        "atom_charges": charges,
        "ionic_structure_factor": structure_factor,
        "num_electrons": np.array(ham.num_electrons),
        "spin_polarized": np.array(ham.spin_polarized),
        "cutoff_energy_ev": np.array(ecut),
        "volume_ang3": np.array(volume),
        "canonical_hash": np.array(entry.canonical_hash()),
    }


class NumpyPlaneWaveExporter:
    """Registry exporter ``numpy_planewave``::

        from qmatbridge.registry import get_exporter

        meta = get_exporter("numpy_planewave").export(entry, path="si.npz")
        entry.exports.append(meta)
    """

    name = "numpy_planewave"

    def export(self, entry: QMatEntry, **options: Any) -> ExportMetadata:
        """Write *entry* to ``path`` (``.npz``) and describe the result.

        Options:
            path:           Output file (required).  ``.npz`` is appended by
                            NumPy if missing, and the reported path includes it.
            max_candidates: Work limit for the enumeration (see
                            :func:`plane_wave_arrays`).
        """
        path = options.pop("path", None)
        max_candidates = options.pop("max_candidates", DEFAULT_MAX_CANDIDATES)
        if options:
            raise TypeError(
                "unexpected option(s) for numpy_planewave: "
                + ", ".join(sorted(options))
            )
        if path is None:
            raise TypeError("numpy_planewave needs path='...npz'")
        np = _numpy()
        arrays = plane_wave_arrays(entry, max_candidates=max_candidates)
        out = os.fspath(path)
        if not out.endswith(".npz"):
            out += ".npz"
        np.savez_compressed(out, **arrays)
        return ExportMetadata(
            framework="numpy",
            format=_FORMAT,
            target_name=f"numpy_planewave_{entry.hamiltonian.num_electrons}e",
            status="complete",
            version=np.__version__,
            exported_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            artifact_path=out,
            metadata={
                "num_plane_waves": int(arrays["g_vectors"].shape[0]),
                "num_atoms": int(arrays["atom_charges"].shape[0]),
                "entry_hash": entry.canonical_hash(),
            },
        )
