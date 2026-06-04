# QMatBridge

**Open-source tools connecting classical materials databases to first-quantized
Hamiltonians for fault-tolerant quantum simulation.**

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

See [`qmatbridge/CONTRIBUTING.md`](https://github.com/QMatBridge/qmatbridge/blob/main/CONTRIBUTING.md)
to get started, and
[GitHub Discussions](https://github.com/QMatBridge/qmatbridge/discussions)
to propose ideas or ask questions.

---

## Status

| Component | Status |
| --- | --- |
| Core schema (`QMatEntry`, `HamiltonianMetadata`, …) | Stable — v0.1 |
| JSON I/O (`qmatbridge.io`) | Stable — v0.1 |
| Materials Project adapter | Stub — v0.2 target |
| OQMD adapter | Stub — v0.3 target |
| OPTIMADE adapter | Planned — v0.3 |
| Hamiltonian exporters | Planned — v0.4 |
| Resource estimation hooks | Planned — v0.5 |
