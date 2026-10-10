# Cross-database deduplication

The same crystal is often stored in several databases, relaxed with slightly different
settings and often in another cell. `qmatbridge.dedup` groups entries that describe one
material.

```python
from qmatbridge.dedup import find_duplicates, deduplicate

groups = find_duplicates(entries)
for g in groups:
    print(g.indices, [(l.kind, l.shared) for l in g.links], len(g.conflicts))

unique = deduplicate(entries)                                   # first of each group
unique = deduplicate(entries, prefer=lambda e: e.reference.provenance.functional != "PBE")
```

## Evidence

| Kind | Meaning |
| --- | --- |
| `shared_identifier` | The entries share an external identifier in `provenance.primary` or `additional_ids` (an ICSD number, a COD id, ...). Needs no atomic positions. An OPTIMADE entry from `mp` also counts as the Materials Project record. |
| `geometry` | The atomic environments agree. Needs `structure.sites` on both entries and equal reduced formulas. |

Grouping is transitive. For an identifier link between entries that both have positions,
`geometry_agrees` records whether the structures also match; `group.conflicts` lists the
links where they do not, which usually means a wrong or shared-by-several-phases
identifier and deserves a look.

## What the geometry test compares

For each atom, the nearest distances to atoms of each element, taken with periodic
images so the result does not depend on the cell. Two structures match when every
distinct environment of one occurs in the other and vice versa, within a relative
distance tolerance `rtol` (default 3 %, which covers the lattice spread between PBE and
PBEsol). The primitive and the conventional cell of one crystal, a shifted origin and a
different atom order all match; rocksalt and zincblende of one composition do not.

It is a fingerprint, not a symmetry analysis: it is not a replacement for a full
structure matcher on borderline cases, and `rtol` is yours to tighten.

Duplicates are duplicates of the *material*. Two entries of one material with different
functionals are grouped, and keep different `canonical_hash()` values.
