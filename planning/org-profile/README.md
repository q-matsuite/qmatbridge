# q-matsuite

**Open-source tools connecting classical materials databases to first-quantized
Hamiltonians for fault-tolerant quantum simulation.**

First project: [**QMatBridge**](https://q-matsuite.com/qmatbridge/).  Site:
[q-matsuite.com](https://q-matsuite.com).

---

## What we build

Fault-tolerant quantum algorithms for materials simulation require Hamiltonians
expressed in precise, reproducible forms — LCU decompositions, plane-wave
representations, sparse operator encodings.  Assembling these from DFT data
today means writing one-off, non-interoperable scripts with no shared
provenance standard.

QMatBridge provides the missing layer: a **neutral intermediate representation**
(`QMatEntry`) that any upstream database adapter can write to and any downstream
quantum compiler or resource estimator can read from.

```
Materials Project ──┐
OQMD              ──┤  adapters ──▶  QMatEntry ──▶  exporters ──▶  OpenFermion
OPTIMADE sources  ──┤                   (NIR)                  ──▶  qualtran
Alexandria        ──┘                                          ──▶  pyLIQTR
```

Every entry records where the material came from, how the Hamiltonian was
constructed, what the oracle costs, and a deterministic canonical hash —
so a benchmark paper can cite a hash and anyone can reproduce the exact
Hamiltonian from it.

---

## Why first-quantized Hamiltonians?

Second-quantized representations grow with the number of orbitals; first-quantized
plane-wave representations scale with the number of plane waves and electrons,
which is more natural for periodic materials in fault-tolerant settings.

The leading fault-tolerant simulation algorithms — qubitization walk operators,
LCU-based Hamiltonian simulation, truncated Dyson series — consume first-quantized
inputs and require explicit quantities like:

- LCU 1-norm **λ** (sets T-count via λ/ε)
- Number of plane waves **N** (sets state-register size)
- Electron count **η** (sets occupation encoding cost)

QMatBridge records all of these directly, field by field, with provenance.

---

## Open-source and community-driven

We are an early-stage project.  The core schema is stabilizing; adapters and
exporters are in progress.  We welcome contributions at any level:

- **Algorithm researchers** who want reproducible Hamiltonians for benchmarks
- **Research software engineers** building quantum-chemistry pipelines
- **Database maintainers** who want to add an adapter for their source
- **Educators** building course materials around fault-tolerant simulation

See [CONTRIBUTING.md](https://github.com/q-matsuite/qmatbridge/blob/main/CONTRIBUTING.md)
to get started, and
[GitHub Discussions](https://github.com/q-matsuite/qmatbridge/discussions)
to propose ideas or ask questions.

---

## Status

| Component | Status |
| --- | --- |
| Core schema (`QMatEntry`, `HamiltonianMetadata`, …) | v0.1; a v0.2 proposal is open for discussion |
| JSON I/O: write and read back, strictly validated | Available |
| Plane-wave utilities | Available |
| Materials Project adapter | Available; validated against the live API for six Tier-1 materials |
| Plugin registry for adapters and exporters | Available |
| OQMD adapter | Stub |
| OPTIMADE adapter | Planned |
| Hamiltonian exporters | Planned |
| Resource estimation hooks | Planned |

Install with `pip install qmatbridge` (latest release on [PyPI](https://pypi.org/project/qmatbridge/)). See the
[roadmap](https://github.com/q-matsuite/qmatbridge#roadmap).
