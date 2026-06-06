# Oracle and Export Model

This page describes how QMatBridge represents Hamiltonian-simulation oracles,
term decompositions, and downstream export targets.  It is intended for
researchers implementing block-encodings, qubitization circuits, sparse-access
oracles, and related fault-tolerant primitives.

---

## Background

Fault-tolerant Hamiltonian simulation algorithms require the Hamiltonian to be
presented in a specific form that the oracle circuit can load.  The dominant
paradigms are:

| Paradigm | Oracle structure | Key quantity |
| --- | --- | --- |
| LCU / qubitization | SELECT + PREPARE | λ = Σ|αₗ| (1-norm) |
| Sparse access | Row oracle + column oracle | d (max row nonzeros) |
| Tensor hypercontraction | Factored PREPARE | rank R |
| Truncated Dyson series | Nested LCU | higher-order λ |

QMatBridge's `OracleMetadata` records which paradigm is being targeted and
carries the numerical quantities needed to estimate T-gate, Toffoli, and qubit
costs analytically.

---

## Term decompositions

A first-quantized plane-wave Hamiltonian has three physical terms:

```
H = T + U + V
  kinetic   electron-nuclear   electron-electron
```

Each is stored as a `TermMetadata` entry in `HamiltonianMetadata.terms`:

```python
from qmatbridge.schema import TermMetadata

T = TermMetadata(
    name="kinetic",
    lambda_one_norm=124.3,          # Ha — LCU coefficient sum for T
    lambda_spectral=91.7,           # Ha — spectral norm
    num_lcu_terms=1849,             # one plane-wave per term
    truncation_threshold=1e-5,
    implementation_notes="Diagonal in momentum basis; loaded via QROM on |p⟩.",
)

U = TermMetadata(
    name="electron_nuclear",
    lambda_one_norm=102.1,
    lambda_spectral=78.6,
    num_lcu_terms=1849 * 2,         # N_pw × N_atoms
    implementation_notes="1/|G| structure factor; QROM on grid index.",
)

V = TermMetadata(
    name="electron_electron",
    lambda_one_norm=89.4,
    lambda_spectral=64.2,
    num_lcu_terms=1849 * 1849 // 2,
)
```

The `coefficient_labels` field stores explicit labels when coefficient-level
detail is available (e.g. for small systems or debug builds):

```python
T_small = TermMetadata(
    name="kinetic",
    coefficient_labels=["T_G(0,0,0)", "T_G(1,0,0)", "T_G(-1,0,0)"],
    lambda_one_norm=12.1,
    num_lcu_terms=3,
)
```

---

## Coefficient collections and SELECT/PREPARE

The LCU decomposition writes H = Σₗ αₗ Uₗ.  The two key oracles are:

**PREPARE**: loads the coefficient distribution into an ancilla register

```
PREPARE |0⟩ = Σₗ √(αₗ/λ) |l⟩
```

**SELECT**: applies the l-th unitary conditioned on the index register

```
SELECT |l⟩|ψ⟩ = |l⟩ Uₗ|ψ⟩
```

`OracleMetadata` captures both sides of this split:

```python
from qmatbridge.schema import OracleMetadata

oracle = OracleMetadata(
    method="lcu",
    oracle_type="SELECT_PREPARE",       # combined walk operator
    lambda_total=315.8,
    num_lcu_terms=3_430_000,
    index_encoding="binary",            # ceil(log2(L)) qubits for index
    coefficient_sampling="alias_sampling",  # Babbush et al. 2018 technique
    eta=1e-3,
    delta_e=1.6e-3,
    num_bits_state=11,
    num_bits_rot=20,
    complexity={
        "toffoli_dominant": True,
        "toffoli_count_formula": "O(lambda * N_pw / delta_e)",
        "ancilla_qubits_approx": 42,
        "reference": "Babbush et al., npj Quantum Information (2019)",
    },
)

The controlled vocabularies for `oracle_type` and `index_encoding` are
defined by the module-level sets `qmatbridge.schema._ORACLE_TYPES` and
`qmatbridge.schema._INDEX_ENCODINGS`.
```

### oracle_type values

| Value | Meaning |
| --- | --- |
| `"SELECT"` | Only the SELECT oracle is described |
| `"PREPARE"` | Only the PREPARE oracle is described |
| `"SELECT_PREPARE"` | Both combined into a qubitization walk operator |
| `"QROM"` | Quantum read-only memory used to load coefficients |
| `"sparse_access"` | Row/column oracle for d-sparse Hamiltonians |

---

## Sparse access patterns

For second-quantized or real-space Hamiltonians where explicit LCU is
impractical, the sparse oracle pattern stores a maximum row nonzero count `d`
and the access oracle structure:

```python
sparse_oracle = OracleMetadata(
    method="sparse",
    oracle_type="sparse_access",
    num_lcu_terms=500,          # max row nonzeros d
    index_encoding="binary",
    implementation_notes=(
        "Row oracle returns the j-th nonzero column index and amplitude "
        "for a given row i.  Compatible with Berry et al. (2012) simulation."
    ),
    complexity={
        "query_cost_T": "O(log N)",
        "simulation_cost": "O(d * norm * t / eps)",
    },
)
```

---

## Index encoding

The `index_encoding` field on `OracleMetadata` records how the term index
register is laid out in qubits.  This matters for SELECT circuit depth and
QROM address decoding.

| Value | Description | Qubit count |
| --- | --- | --- |
| `"binary"` | Standard binary encoding | ⌈log₂ L⌉ |
| `"unary"` | One-hot / thermometer code | L |
| `"one_hot"` | Explicit one-hot (L = 2ᵏ) | L |

For plane-wave Hamiltonians, `"binary"` is standard.  For small-L systems or
when AND gates are more expensive, `"unary"` may be preferred.

---

## Coefficient sampling (PREPARE)

`OracleMetadata.coefficient_sampling` is a short string indicating the
technique used to implement PREPARE.

| Value | Technique |
| --- | --- |
| `"alias_sampling"` | Alias method (near-uniform sampling, Babbush 2018) |
| `"QROM_direct"` | Direct QROM load of coefficient amplitudes |
| `"uniform_superposition"` | All terms weighted equally (approximation) |
| `"coherent_alias"` | Coherent alias sampling with fewer ancillae |

---

## Complexity annotations

`OracleMetadata.complexity` is a free-form dict for annotated resource
quantities.  Recommended keys:

```python
complexity = {
    # Asymptotic counts (strings)
    "T_count_formula":      "O(lambda / delta_e * polylog(...))",
    "toffoli_count_formula": "O(lambda * N / delta_e)",

    # Concrete numeric estimates (ints / floats)
    "toffoli_count":        4_200_000,
    "ancilla_qubits":       52,
    "logical_qubits_total": 1234,

    # Provenance
    "reference": "Berry et al., Quantum 3, 208 (2019)",
    "estimated_by": "qmatbridge:0.1",
}
```

These annotations are not validated by QMatBridge; they are stored as
provenance for downstream resource-estimation pipelines.

---

## Export targets and status

`ExportMetadata` records every downstream artifact generated from a
`QMatEntry`.  The `status` field tracks the lifecycle:

```python
from qmatbridge.schema import ExportMetadata

exports = [
    ExportMetadata(
        framework="openfermion",
        format="InteractionOperator",
        target_name="openfermion_Si_8e_520eV",
        status="pending",
    ),
    ExportMetadata(
        framework="qualtran",
        format="lcu_coefficients",
        target_name="qualtran_Si_lcu",
        status="complete",
        version="0.4.0",
        exported_at="2026-06-03T12:00:00Z",
        artifact_path="artifacts/Si_lcu_qualtran.npz",
    ),
    ExportMetadata(
        framework="qiskit",
        format="SparsePauliOp",
        target_name="qiskit_Si_sparse_pauli",
        status="pending",
        metadata={"num_paulis": 58_000, "truncated": True},
    ),
]
```

### Supported status values

| Status | Meaning |
| --- | --- |
| `"pending"` | Export has not yet been run |
| `"complete"` | Export succeeded; `artifact_path` should be set |
| `"failed"` | Export was attempted and failed; check `metadata` for error |

### Qiskit-style workflows

For Qiskit users, the expected export path is:

1. Set `ExportMetadata.framework = "qiskit"`, `format = "SparsePauliOp"` or
   `"FermionOperator"`.
2. The QMatBridge exporter (planned v0.4) produces a serialized
   `SparsePauliOp` (`.npz` or `.json`).
3. `artifact_path` points to that file; downstream Qiskit circuits load it
   via `SparsePauliOp.from_list(...)`.

For fault-tolerant resource estimation outside Qiskit, the export format
`"lcu_coefficients"` produces a flat array of (label, coefficient) pairs
that `qualtran` or `pyLIQTR` can consume directly.

---

## Putting it together

A `QMatEntry` with full oracle and export metadata:

```python
from qmatbridge.schema import (
    QMatEntry, OracleMetadata, TermMetadata, ExportMetadata,
    HamiltonianMetadata, BasisMetadata,
)

oracle = OracleMetadata(
    method="lcu",
    oracle_type="SELECT_PREPARE",
    lambda_total=315.8,
    num_lcu_terms=3_430_000,
    index_encoding="binary",
    coefficient_sampling="alias_sampling",
    eta=1e-3,
    delta_e=1.6e-3,
    num_bits_state=11,
    num_bits_rot=20,
    terms=[
        TermMetadata(
            name="kinetic",
            lambda_one_norm=124.3,
            num_lcu_terms=1849,
            implementation_notes="QROM on |p⟩ diagonal.",
        ),
        TermMetadata(
            name="electron_electron",
            lambda_one_norm=89.4,
            num_lcu_terms=1_709_400,
        ),
        TermMetadata(
            name="electron_nuclear",
            lambda_one_norm=102.1,
            num_lcu_terms=3698,
        ),
    ],
    complexity={
        "toffoli_count": 4_200_000,
        "ancilla_qubits": 52,
        "reference": "Babbush et al. (2019)",
    },
)

# entry.hamiltonian.oracle = oracle
# entry.exports = [ExportMetadata(framework="qualtran", format="lcu_coefficients", ...)]
```

---

## Schema reference

| Class | New fields (v0.1) |
| --- | --- |
| `TermMetadata` | `coefficient_labels`, `implementation_notes` |
| `OracleMetadata` | `oracle_type`, `index_encoding`, `coefficient_sampling`, `complexity` |
| `ExportMetadata` | `target_name`, `status` |

See [qmatbridge/schema.py](../qmatbridge/schema.py) for full field documentation.
