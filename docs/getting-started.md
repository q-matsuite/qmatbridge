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

## Read an entry back

```python
from qmatbridge.io import read_entry_json

back = read_entry_json("silicon.json")
assert back == entry                                   # the entry from the example above
assert back.canonical_hash() == entry.canonical_hash()
```

Reading is strict: unknown fields, missing required fields, wrongly typed values and an
unsupported `schema_version` raise `EntryFormatError` (a `ValueError`) whose message names
the file and the offending field, for example
`wrong.json: hamiltonian.num_electrons: expected an integer, got str`. Nothing is silently
dropped or coerced, except that an integer is accepted where a float is expected.

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

## What the hash covers

`QMatEntry.canonical_hash()` is a SHA-256 over **eleven fields**: the source and identifier,
the functional, the reduced formula, the space-group number, the electron count, spin
polarization, the basis type, the cutoff energy, the number of bands and the oracle η.
Changing any of them changes the hash; nothing else does (tags, exports, retrieval time and
free-form metadata are ignored).

It identifies the **calculation setup recorded in the entry**. The lattice parameters, atomic
positions, species list, pseudopotential family and plane-wave count are *not* hashed, so two
groups can check that they used the same source record and settings, but an identical hash does
not by itself prove identical coordinates. Whether to include positions is an open design
question: see [Discussion #24](https://github.com/q-matsuite/qmatbridge/discussions/24).
