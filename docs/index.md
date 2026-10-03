# QMatBridge

**A Python library for bridging classical materials databases to first-quantized
Hamiltonians for fault-tolerant quantum simulation.**

Fault-tolerant Hamiltonian-simulation research needs realistic electronic-structure
inputs, and the one-off scripts that produce them rarely record where the data came
from. QMatBridge defines a **neutral intermediate representation** (`QMatEntry`) that
any database adapter can write and any downstream compiler or resource estimator can
read, with provenance and a deterministic hash attached.

```text
Materials Project ─┐
OQMD              ─┤  adapters ─▶ QMatEntry (NIR) ─▶ exporters ─▶ OpenFermion / qualtran / pyLIQTR
OPTIMADE sources  ─┘
```

| Section | What you will find |
| --- | --- |
| [Getting started](getting-started.md) | Install, build an entry, fetch from Materials Project |
| [Vision](vision.md) | Design rationale and constraints |
| [Oracle model](oracle-model.md) | How LCU / qubitization metadata is represented |
| [Adapters](adapters.md) | Upstream sources and their status |
| [API reference](api.md) | Generated from the source docstrings |

!!! note "Status"
    Early-stage. The schema and JSON I/O are functional; the Materials Project
    adapter is implemented but not yet validated against the live API in CI;
    exporters are planned. See the
    [roadmap](https://github.com/q-matsuite/qmatbridge#roadmap).

---

Created and maintained by [Roberto Reis](https://github.com/rmsreis) ([@rmsreis](https://github.com/rmsreis)).
