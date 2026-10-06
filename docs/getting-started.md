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

`QMatEntry.canonical_hash()` is a SHA-256 over **eleven setup fields**: the source and
identifier, the functional, the reduced formula, the space-group number, the electron count,
spin polarization, the basis type, the cutoff energy, the number of bands and the oracle η.

**Geometry is hashed when the entry records it.** If `structure.sites` is non-empty (schema
0.2; the Materials Project adapter fills it), the lattice parameters and the fractional
position of every atom are hashed too. They are written as fixed 6-decimal strings with
coordinates wrapped into [0, 1) and the sites sorted, so site order and numerical noise below
10⁻⁶ do not matter. An entry **without** `sites` hashes only the eleven fields, exactly as in
0.2.0, so entries stored before this change keep their hash.

Changing any hashed field changes the hash; nothing else does (tags, exports, retrieval time
and free-form metadata are ignored). The pseudopotential family and the plane-wave count are
not hashed, and the hash is not invariant to a different choice of cell or origin: the same
crystal described with a shifted origin is a different entry. The policy was decided in
[Discussion #24](https://github.com/q-matsuite/qmatbridge/discussions/24).
