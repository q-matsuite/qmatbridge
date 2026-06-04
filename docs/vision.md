# QMatBridge — Project Vision

## Problem Statement

Fault-tolerant quantum algorithms for materials simulation require Hamiltonians that are:

1. **Derived from authoritative DFT data** — not toy models
2. **Expressed in a form amenable to block-encoding or qubitization** — e.g. plane-wave
   first-quantized, sparse second-quantized, or LCU decompositions
3. **Annotated with provenance** — so benchmark results are reproducible and comparable

Today, researchers hand-roll bespoke scripts to pull DFT outputs, reformat them, and
feed them into quantum compilers. These scripts are rarely shared, seldom reproducible,
and almost never interoperable with more than one quantum framework.

QMatBridge fills this gap.

---

## Design Philosophy

### Neutral Intermediate Representation (NIR)

The core of QMatBridge is `QMatEntry` — a dataclass that captures *what* the material
is and *how* the Hamiltonian was computed, without committing to any particular operator
representation. Downstream exporters convert an entry into the format they need.

This mirrors the compiler IR pattern: one shared representation, many backends.

### Thin Adapters, Not Fat Importers

Each upstream database (Materials Project, AFLOW, ICSD, ASE trajectories) gets a
minimal adapter that maps database-native objects into `QMatEntry` instances.
Adapters do as little transformation as possible — they capture provenance, not physics.

### Optional Dependencies, Hard Core

The `qmatbridge` core (`schema.py`) has **zero external dependencies**. Heavy extras
(pymatgen, mp-api, openfermion) live behind optional install groups so a CI environment
or a downstream package can import the schema without dragging in gigabytes of libraries.

### Reproducibility by Default

Every `QMatEntry` can compute a canonical hash over its physically meaningful fields.
Benchmark papers can cite the hash; anyone with QMatBridge can regenerate the entry.

---

## Scope (v0.x)

**In scope:**
- Periodic bulk materials, plane-wave basis
- First-quantized Hamiltonian representation (kinetic + Coulomb in reciprocal space)
- Second-quantized sparse representation (for small cells)
- Resource-estimation metadata (eta, cutoff, electron count)

**Out of scope (for now):**
- Gaussian / LCAO basis sets
- Molecular (non-periodic) systems
- Excited-state / TDDFT Hamiltonians
- Real-time dynamics drivers

---

## Relationship to Existing Tools

| Tool | Role relative to QMatBridge |
|------|------------------------------|
| `pymatgen` | Structure representation; QMatBridge consumes it via adapters |
| `mp-api` | Database client; wrapped by the Materials Project adapter |
| `OpenFermion` | Downstream consumer; QMatBridge exports to its operator types |
| `qualtran` / `pyLIQTR` | Resource estimation; QMatBridge feeds Hamiltonian parameters |
| `ASE` | Alternative structure source; thin adapter planned |

QMatBridge is intentionally **not** a quantum compiler, a DFT code, or a database.
It is the bridge between those worlds.

---

## Governance Principles

- All breaking changes to `QMatEntry` fields require a minor version bump and a
  migration note in the changelog.
- Adapters for closed-access databases (ICSD) must not include any proprietary data;
  they only define the interface.
- Benchmark data files committed to the repo must be derived from open-access sources.
