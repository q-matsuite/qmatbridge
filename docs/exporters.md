# Exporters

An exporter turns a `QMatEntry` into a downstream format and returns an
`ExportMetadata` describing the artifact. Attach it with `entry.exports.append(meta)`;
exports are not part of the entry's fingerprint. Both exporters below need the entry to
carry atomic positions and valence charges that sum to `num_electrons` (schema 0.3).

```python
from qmatbridge.registry import get_exporter

meta = get_exporter("numpy_planewave").export(entry, path="si.npz")
```

## `numpy_planewave`

| | |
| --- | --- |
| **Install** | `pip install "qmatbridge[numpy]"` |
| **Module** | `qmatbridge.exporters.numpy_planewave` |
| **Output** | `.npz` with the G-vectors, kinetic energies, ion positions and charges, and the ionic structure factor |

The plane-wave set matches `BasisMetadata.num_plane_waves` exactly. The array layout
is documented in the module docstring.

## `openfermion`

| | |
| --- | --- |
| **Install** | `pip install "qmatbridge[openfermion]"` |
| **Module** | `qmatbridge.exporters.openfermion_pw` |
| **Output** | `.npz` with the constant and the one- and two-body tensors of an `InteractionOperator`, in Hartree atomic units |

```python
from qmatbridge.exporters.openfermion_pw import (
    interaction_operator,
    load_interaction_operator,
)

op = interaction_operator(entry, ecut_ev=30.0)        # an openfermion.InteractionOperator
meta = get_exporter("openfermion").export(entry, path="si_of.npz", ecut_ev=30.0)
op = load_interaction_operator(meta.artifact_path)    # read it back
```

### What the Hamiltonian is

For plane waves at the Γ point, the exporter writes the kinetic energy, the
electron-ion potential, the electron-electron Coulomb interaction (momentum conserving,
`q ≠ 0`) and the Ewald energy of the ions as the constant. The one-body and the
two-body terms agree term by term with OpenFermion's own `plane_wave_hamiltonian`
(checked in the test suite on a cubic cell; OpenFermion's plane waves are
`exp(-i k·r)` and ours `exp(+i G·r)`, so mode `k` corresponds to `G = -k`).

**It is a model, not the DFT Hamiltonian.** The ions are point charges with strength
equal to the entry's per-species valence charge; the entry holds no pseudopotential
form factor, so none is applied. The `q = 0` terms cancel for a neutral cell and are
dropped. The result is a faithful *Coulomb* plane-wave Hamiltonian of the cell for
testing algorithms and estimating sizes, and it should not be used to reproduce the
source database's energies.

### Size and options

The two-body tensor has `(2N)^4` entries for `N` plane waves (`N^4` with
`spinless=True`), so only small bases are practical. The exporter selects the plane
waves with kinetic energy up to `ecut_ev` (default and maximum: the entry's cutoff),
and **refuses** more than `max_plane_waves` (default 32) instead of allocating
gigabytes. Spin orbital `2i + s` is plane wave `i` with spin `s`.
