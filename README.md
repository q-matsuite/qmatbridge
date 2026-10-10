# QMatBridge

**A Python library for bridging classical materials databases to first-quantized
Hamiltonians for fault-tolerant quantum simulation.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/q-matsuite/qmatbridge/actions/workflows/python-package.yml/badge.svg)](https://github.com/q-matsuite/qmatbridge/actions)
[![PyPI](https://img.shields.io/pypi/v/qmatbridge.svg)](https://pypi.org/project/qmatbridge/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23192772.svg)](https://doi.org/10.5281/zenodo.23192772)
[![Website](https://img.shields.io/badge/website-q--matsuite.com-5fd4dd.svg)](https://q-matsuite.com/qmatbridge/)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://q-matsuite.com/qmatbridge/docs/)

> **Status:** early-stage, active development — schema is stabilizing, adapters
> are stubs, exporters are planned.  The core NIR and I/O layer are functional.
> Breaking changes to `QMatEntry` before v1.0 will be announced in
> [CHANGELOG.md](CHANGELOG.md) and accompanied by migration notes.

---

## Why QMatBridge exists

Research groups developing fault-tolerant Hamiltonian-simulation algorithms —
block-encodings, qubitization variants, truncated Dyson series methods — need
realistic electronic-structure Hamiltonians to test and benchmark their
primitives.  The standard path is to write one-off scripts that pull DFT data
from the Materials Project or similar databases, reformat it, and feed it into
a quantum compiler.

These scripts are rarely shared, almost never interoperable with more than one
quantum framework, and often omit the provenance information needed to reproduce
or compare results.  When two groups report T-gate counts for "silicon", there
is no standard way to verify they used the same Hamiltonian.

QMatBridge addresses this by providing a **neutral intermediate representation
(NIR)** that any upstream database adapter can write to and any downstream
quantum compiler or resource estimator can read from, with full provenance
baked in.

---

## Core idea

```text
  Materials Project  ──┐
  OQMD               ──┤  adapters  ──▶  QMatEntry (NIR)  ──▶  exporters  ──▶  OpenFermion
  OPTIMADE sources   ──┤                                                   ──▶  qualtran
  Alexandria         ──┘                                                   ──▶  pyLIQTR
                                                                           ──▶  Qiskit
```

A `QMatEntry` records:

- **where** the material came from (`SourceProvenance` — database, functional,
  pseudopotential, code version, retrieval timestamp)
- **what** it looks like (`StructureMetadata` — formula, lattice, spacegroup)
- **how** the Hamiltonian is constructed (`BasisMetadata` — plane-wave cutoff,
  basis size)
- **what the oracle costs** (`OracleMetadata` — LCU 1-norm λ, term breakdown,
  SELECT/PREPARE circuit parameters, complexity annotations)
- **where it has been exported** (`ExportMetadata` — framework, format, status,
  artifact path)

Every entry carries a deterministic `canonical_hash()` over eleven setup fields
(source record, functional, electrons, basis cutoff and a few more), plus the lattice and
atomic positions when the entry records them, so that benchmark results can be traced to a
specific recorded calculation. See
[what the hash covers](docs/getting-started.md#what-the-hash-covers).

---

## Who it is for

QMatBridge is written for:

- **Algorithm researchers** implementing block-encodings, qubitization circuits,
  LCU decompositions, and related fault-tolerant primitives who need real
  materials data without building a database-integration layer themselves.
- **Research software engineers** building quantum-chemistry / quantum-computing
  pipelines who need a stable, citable intermediate format between the DFT world
  and the circuit world.
- **Resource estimation groups** running systematic T-count and qubit studies
  across a library of materials, who need reproducible, provenance-rich
  Hamiltonian records.

If you are looking for a general materials informatics library, use
[pymatgen](https://pymatgen.org) or [ASE](https://wiki.fysik.dtu.dk/ase/).
QMatBridge is intentionally narrow: it is a bridge, not a database.

---

## Current scope

**In scope (v0.1):**

- Periodic bulk materials in a plane-wave basis
- First-quantized Hamiltonian representation (T + U + V in reciprocal space)
- LCU / qubitization oracle metadata
- JSON serialization with canonical entry hashes
- Materials Project adapter (structure + plane-wave Hamiltonian metadata); OQMD adapter (live fetch, recorded-response tested)
- Raw plane-wave NumPy exporter; OpenFermion `InteractionOperator` exporter (a small point-ion plane-wave model)
- Zero required dependencies in the core schema

**Out of scope (for now):**

- Gaussian / LCAO / real-space basis sets
- Molecular (non-periodic) systems
- Excited-state or TDDFT Hamiltonians
- Alexandria HSE06 / r²SCAN adapter (planned v0.4)
- qualtran / pyLIQTR exporters (planned v0.5)

---

## Design principles

**Provenance-first.**  Every `QMatEntry` records the exact upstream source,
DFT functional, pseudopotential family, and retrieval timestamp.  The
`canonical_hash()` method produces a stable SHA-256 digest over the physically
meaningful fields so that published results can be precisely reproduced.

**Open and interoperable.**  The core schema has zero required dependencies.
Adapters for upstream databases and exporters for downstream frameworks are
optional extras — install only what you need.  The NIR is designed to be
targeted by any adapter or consumed by any exporter without coupling the two.

**Benchmark-oriented.**  Field names, norm conventions, and oracle metadata
types are chosen to align with the quantities reported in fault-tolerant
resource-estimation literature (LCU 1-norm λ, plane-wave count N,
rotation-precision bits b_r).  The library should make it easy to reproduce
or extend a published benchmark, not just run a new one.

**Representation-aware.**  `OracleMetadata` distinguishes between LCU,
qubitization, sparse-access, and tensor-hypercontraction decompositions.
`TermMetadata` stores per-physical-term norms so that methods that weight
T, U, and V differently can extract exactly the quantities they need.

**Community-driven.**  The schema is a shared contract.  Changes to
`QMatEntry`, `MaterialReference`, or `HamiltonianMetadata` require a public
discussion period and a minor-version bump.  The governance model is documented
in [GOVERNANCE.md](GOVERNANCE.md); design discussions happen in GitHub
Discussions before any code is written.

---

## Getting started

### Installation

```bash
pip install qmatbridge             # from PyPI; the core has no required dependencies
pip install "qmatbridge[mp]"       # + Materials Project adapter (mp-api, pymatgen); use Python 3.11+
```

Optional extras:

```bash
pip install "qmatbridge[numpy]"        # raw plane-wave NumPy exporter
pip install "qmatbridge[openfermion]"  # OpenFermion exporter
```

To work on QMatBridge itself, install from source:

```bash
git clone https://github.com/q-matsuite/qmatbridge.git
cd qmatbridge
pip install -e ".[dev]"
```

### API keys

QMatBridge ships no credentials.  To fetch from the Materials Project you need your
own free API key (`export MP_API_KEY=...`); reading entries and the committed
benchmark fixtures needs none.  See [docs/api-keys.md](docs/api-keys.md) for which
sources need a key, how to keep it out of git, and data-licence/attribution notes.

### Minimal example

```python
from qmatbridge.schema import (
    ExternalIdentifier, SourceProvenance,
    LatticeMetadata, StructureMetadata,
    BasisMetadata, HamiltonianMetadata,
    MaterialReference, QMatEntry,
)
from qmatbridge.io import write_entry_json

provenance = SourceProvenance(
    primary=ExternalIdentifier(
        source="materials_project", identifier="mp-149"
    ),
    functional="PBE",
    pseudopotential="PAW_PBE",
    code="VASP",
)

structure = StructureMetadata(
    formula_reduced="Si",
    formula_unit_cell="Si2",
    num_sites=2,
    species=["Si", "Si"],
    lattice=LatticeMetadata(
        a=3.867, b=3.867, c=3.867,
        alpha=60.0, beta=60.0, gamma=60.0,
        spacegroup_number=227, spacegroup_symbol="Fd-3m",
    ),
)

hamiltonian = HamiltonianMetadata(
    num_electrons=8,
    spin_polarized=False,
    basis=BasisMetadata(type="plane_wave", cutoff_energy_ev=520.0),
    num_bands=16,
)

entry = QMatEntry(
    reference=MaterialReference(provenance=provenance, structure=structure),
    hamiltonian=hamiltonian,
    tags=["silicon", "benchmark"],
)

print(entry)                      # QMatEntry(formula='Si', source='materials_project', ...)
print(entry.canonical_hash())     # deterministic SHA-256

write_entry_json(entry, "silicon.json")   # full nested JSON, 2-space indent
```

See [`examples/minimal_entry.py`](examples/minimal_entry.py) for a fully
populated silicon entry including oracle metadata and term breakdown.

---

## Repository layout

```text
qmatbridge/
├── qmatbridge/
│   ├── schema.py                  # Neutral intermediate representation (NIR)
│   ├── io.py                      # JSON serialization utilities
│   ├── basis.py                   # Plane-wave counting utilities
│   ├── adapters/
│   │   ├── materials_project.py   # Materials Project adapter
│   │   └── oqmd.py                # OQMD adapter
│   └── exporters/
│       ├── numpy_planewave.py     # Raw plane-wave arrays (.npz)
│       └── openfermion_pw.py      # OpenFermion InteractionOperator
├── docs/
│   ├── vision.md                  # Design rationale and architectural constraints
│   ├── adapters.md                # Upstream adapter documentation
│   └── oracle-model.md            # Oracle abstraction and export model
├── examples/
│   ├── minimal_entry.py           # Silicon QMatEntry with full oracle metadata
│   └── outputs/                   # Generated CSV/JSON/PNG artifacts
├── benchmarks/
│   ├── README.md                  # Benchmark methodology and Tier-1 material plan
│   ├── tier1.py                   # Tier-1 specification
│   └── build_tier1_fixtures.py    # Live fixture generator (needs MP_API_KEY)
├── mkdocs.yml                     # Documentation site configuration
├── planning/
│   └── initial_issues.md          # Scoped GitHub issue set for v0.1–v0.4
└── .github/workflows/
    └── python-package.yml         # CI: lint (ruff + mypy) + tests on 3.10–3.12
```

---

## Roadmap

### v0.1 — Schema and scaffold *(released)*

- [x] Core dataclasses: `MaterialReference`, `HamiltonianMetadata`, `QMatEntry`
- [x] Oracle and term metadata: `OracleMetadata`, `TermMetadata`, `ExportMetadata`
- [x] JSON serialization via `qmatbridge.io`
- [x] Canonical entry hash (`QMatEntry.canonical_hash()`)
- [x] Adapter stubs: Materials Project, OQMD
- [x] CI: ruff, mypy, pytest on Python 3.10–3.12
- [x] JSON round-trip regression fixtures
- [x] Oracle convention vocabulary (`oracle_type`, `index_encoding`)

### v0.2 — Materials Project live integration *(released as 0.2.0)*

- [x] `fetch_structure_metadata_from_mp`, `fetch_hamiltonian_metadata_from_mp` and
      `fetch_entry_from_mp`, validated against the live API
- [x] Plane-wave count utility (`num_plane_waves_from_ecut`)
- [x] Tier-1 benchmark fixtures (Si, GaN, LiCoO₂, LiFePO₄, NaCl, BaTiO₃; LiH, Fe, MgO, TiO₂ planned)
      with nightly live drift checks
- [x] Entry reader (`read_entry_json`) and a plugin registry for adapters and exporters
- [x] MkDocs documentation site, deployed with the landing page

### v0.3 — Atomic positions and a geometry-aware hash *(released as 0.3.0)*

- [x] Schema 0.2: `SiteMetadata` and `StructureMetadata.sites` (fractional coordinates)
- [x] `canonical_hash()` covers lattice and positions when an entry records them; entries
      without positions keep their old hash
- [x] Python and website JavaScript produce identical hashes (tested under Node)
- [x] Tier-1 fixtures and the website carry atomic positions
- [x] Per-species valence charges: `HamiltonianMetadata.valence_charges`, schema 0.3 (released in 0.4.0; issue #13)

### v0.4 — OPTIMADE, OQMD, and Alexandria adapters

- [x] Generic OPTIMADE adapter (AFLOW, JARVIS, NOMAD, MC3D, ...; released in 0.5.0, checked live on MP and Alexandria)
- [x] OQMD live fetch (released in 0.4.0; recorded-response tested, live check owed)
- [ ] Alexandria: PBE and PBEsol are reachable through the OPTIMADE adapter; HSE06 / r²SCAN and the full ~4.5 M set remain
- [ ] Cross-database deduplication via shared ICSD numbers

### v0.5 — Hamiltonian exporters

- [x] OpenFermion `InteractionOperator` exporter (point-ion plane-wave model; released in 0.6.0)
- [x] Raw plane-wave arrays exporter (NumPy `.npz`; released in 0.4.0)
- [ ] LCU coefficient export for `qualtran` / `pyLIQTR`

### v0.6 — Resource estimation hooks

- [ ] T-count and Toffoli estimation interface
- [ ] Qubit footprint estimator
- [ ] Direct integration with `qualtran` / `pyLIQTR` resource analysis

### Beyond v0.6

- Gaussian and real-space basis support
- Defect and surface slab geometries
- Community adapter registry (entry-point group)

---

## Community

| Document | Purpose |
| --- | --- |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to open issues, propose schema changes, and submit pull requests |
| [GOVERNANCE.md](GOVERNANCE.md) | Roles, decision process, and release policy |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards and enforcement |
| [SECURITY.md](SECURITY.md) | Private vulnerability reporting |
| [SUPPORT.md](SUPPORT.md) | Where to ask questions vs. file bugs |
| [GitHub Discussions](https://github.com/q-matsuite/qmatbridge/discussions) | Q&A, design proposals, and architecture discussions |

Contributions are welcome at any level — bug reports, adapter implementations,
documentation improvements, and benchmark additions.  Please read
[CONTRIBUTING.md](CONTRIBUTING.md) and the [project vision](docs/vision.md)
before opening a large pull request.

---

## Citation

QMatBridge does not yet have a formal publication.  If you use it in
academic work, please cite the repository directly:

```bibtex
@software{qmatbridge,
  author       = {{dos Reis}, Roberto},
  organization = {q-matsuite},
  title   = {{QMatBridge}: A bridge from classical materials databases to
             first-quantized Hamiltonians for quantum simulation},
  url     = {https://github.com/q-matsuite/qmatbridge},
    version = {0.6.0},
    doi     = {10.5281/zenodo.23192772},
  year    = {2026},
}
```

A citable release and, if the project grows, a JOSS submission are planned
once the v0.2 Materials Project adapter is complete and the API is stable.

---

## Author

Created and maintained by [Roberto dos Reis](https://www.robertodosreis.com), Department of Materials Science and Engineering, Northwestern University ([@rmsreis](https://github.com/rmsreis)).

---

## License

MIT — see [LICENSE](LICENSE).
