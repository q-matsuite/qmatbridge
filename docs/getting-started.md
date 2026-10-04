# Getting started

## Install

```bash
git clone https://github.com/q-matsuite/qmatbridge.git
cd qmatbridge
pip install -e ".[dev]"
pip install -e ".[mp]"   # Materials Project adapter (mp-api, pymatgen)
```

## Build an entry by hand

```python
from qmatbridge.schema import (
    ExternalIdentifier, SourceProvenance, LatticeMetadata, StructureMetadata,
    BasisMetadata, HamiltonianMetadata, MaterialReference, QMatEntry,
)
from qmatbridge.io import write_entry_json

entry = QMatEntry(
    reference=MaterialReference(
        provenance=SourceProvenance(
            primary=ExternalIdentifier("materials_project", "mp-149"),
            functional="PBE", pseudopotential="PAW_PBE", code="VASP",
        ),
        structure=StructureMetadata(
            formula_reduced="Si", formula_unit_cell="Si2", num_sites=2,
            species=["Si", "Si"],
            lattice=LatticeMetadata(
                a=3.867, b=3.867, c=3.867, alpha=60, beta=60, gamma=60,
                spacegroup_number=227, spacegroup_symbol="Fd-3m",
            ),
        ),
    ),
    hamiltonian=HamiltonianMetadata(
        num_electrons=8, spin_polarized=False,
        basis=BasisMetadata(type="plane_wave", cutoff_energy_ev=520.0),
    ),
)
print(entry.canonical_hash())
write_entry_json(entry, "silicon.json")
```

## Fetch from the Materials Project

You need your own (free) Materials Project API key; QMatBridge does not provide one.
See [API keys and licences](api-keys.md).

```bash
export MP_API_KEY=...
```

```python
from qmatbridge.adapters.materials_project import fetch_entry_from_mp

entry = fetch_entry_from_mp("mp-149", tags=["silicon"])
print(entry.hamiltonian.basis.num_plane_waves)
```

## Count plane waves

```python
from qmatbridge.basis import num_plane_waves_from_ecut

n = num_plane_waves_from_ecut(entry.reference.structure.lattice, 520.0)
```

`method="exact"` (default) enumerates the reciprocal lattice at Γ;
`method="estimate"` uses the continuum formula `V·k_c³ / 6π²`.

## Hash semantics

`QMatEntry.canonical_hash()` is a SHA-256 over the physically meaningful fields, so
two groups reporting results for "silicon" can check they used the same Hamiltonian.
