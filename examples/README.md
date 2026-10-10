# Examples

Runnable examples that demonstrate the QMatBridge schema and I/O utilities.
All examples use only the `qmatbridge` core — no optional extras required.

---

## minimal_entry.py

**What it demonstrates:**

Constructs a complete `QMatEntry` for bulk silicon (Materials Project mp-149)
using every layer of the v0.1 schema:

| Schema object | Content |
| --- | --- |
| `ExternalIdentifier` | Materials Project (`mp-149`) and ICSD (`51688`) cross-reference |
| `SourceProvenance` | PBE functional, PAW_PBE pseudopotentials, VASP 6.3.2 |
| `LatticeMetadata` | Diamond-cubic primitive cell, *a* = 3.867 Å, Fd-3m (227) |
| `StructureMetadata` | 2-site Si₂ unit cell, periodic |
| `BasisMetadata` | Plane-wave basis, 520 eV cutoff, 1849 plane waves |
| `TermMetadata` | Kinetic, electron–electron, and electron–nuclear λ₁ norms |
| `OracleMetadata` | LCU decomposition, λ_total = 315.8 Ha, resource estimate fields |
| `HamiltonianMetadata` | 8 electrons, 16 bands, non-spin-polarized |
| `QMatEntry` | Top-level record with canonical hash and tags |

It also exercises `qmatbridge.io`:

- `to_dict()` — full recursive conversion to a plain Python dict
- `write_entry_json()` — serializes the entry to `silicon_entry.json`

**Run:**

```bash
python examples/minimal_entry.py
```

**Output files produced:**

| File | Description |
| --- | --- |
| `examples/silicon_entry.json` | Full JSON serialization of the silicon `QMatEntry` |

---

## reproducibility_checks.py

**What it demonstrates:**

Shows how `QMatEntry.canonical_hash()` behaves for benchmark reproducibility:

- **Stability:** two equivalent entries produce the same hash.
- **Sensitivity:** changing a physically meaningful field changes the hash.

The example constructs a compact silicon entry, clones it, mutates a single
basis parameter (`cutoff_energy_ev`), and prints the three hashes for direct
comparison.

It also writes a baseline JSON artifact using `write_entry_json()`.

**Run:**

```bash
python examples/reproducibility_checks.py
```

**Output files produced:**

| File | Description |
| --- | --- |
| `examples/outputs/reproducibility_entry.json` | Baseline JSON artifact for the reproducibility check |

---

## material_selection_visual.py

**What it demonstrates:**

Solves a practical benchmark-planning problem:

- You have multiple candidate materials.
- You want to decide which one to simulate first.
- You need a quick, interpretable visual comparison.

The script builds several `QMatEntry` candidates, computes a simple resource
proxy from oracle metadata, ranks all materials, and prints:

- a ranked plain-text table
- an ASCII horizontal bar chart (shorter bar = lower estimated cost)
- notebook-friendly export files (CSV + JSON)
- a matplotlib PNG bar chart for reports/slides

**Run:**

```bash
python examples/material_selection_visual.py
```

**Metric used:**

```text
t_gate_proxy = lambda_total / delta_e
qubits_proxy = num_bits_state + num_bits_rot
score = t_gate_proxy * (1 + qubits_proxy / 100)
```

Lower `score` is treated as better for initial benchmarking.

**Output files produced:**

| File | Description |
| --- | --- |
| `examples/outputs/material_ranking.csv` | Ranked table for notebook plotting (`pandas.read_csv`) |
| `examples/outputs/material_ranking.json` | Same ranking as JSON records |
| `examples/outputs/material_ranking.png` | Matplotlib horizontal bar chart |

---

## pareto_frontier.py

**What it demonstrates:**

Solves a multi-objective benchmark selection problem where two objectives must
be minimized at the same time:

- `t_gate_proxy` (algorithmic cost proxy)
- `qubits_proxy` (space/resource proxy)

The script computes the Pareto-optimal set (non-dominated candidates), prints
Pareto membership in a table, and exports data for notebook analysis.

**Run:**

```bash
python examples/pareto_frontier.py
```

**Output files produced:**

| File | Description |
| --- | --- |
| `examples/outputs/pareto_candidates.csv` | Candidate metrics with `is_pareto_optimal` flag |
| `examples/outputs/pareto_candidates.json` | Same data in JSON record form |
| `examples/outputs/pareto_frontier.png` | Scatter plot with highlighted Pareto frontier |

---

## sensitivity_analysis.py

**What it demonstrates:**

Identifies which input control most strongly influences estimated quantum
simulation resource cost for a first-quantized Hamiltonian benchmark.
The example applies a one-factor-at-a-time (OFAT) sweep over three parameters
— plane-wave cutoff energy, energy precision target, and number of bands —
while holding all others at a Si-like baseline. It then computes:

- a **tornado impact ranking** (absolute and relative score range per parameter)
- **local arc elasticities** at the baseline (dimensionless sensitivity coefficients)
- a **composite score** aggregating T-gate and qubit proxies into a single scalar

All proxy models are explicitly documented with no hidden constants;
every formula is encoded in `compute_proxies()` and recorded in the JSON
metadata artifact for independent verification.

**Run:**

```bash
python examples/sensitivity_analysis.py
```

**Proxy models used:**

```text
num_plane_waves  = N_PW_base × (cutoff_ev / cutoff_ev_base)^1.5
num_bits_state   = ceil(log2(num_plane_waves))
num_bits_rot     = ceil(-log2(delta_e)) + 10
lambda_total     = lambda_base × (cutoff_ev / cutoff_ev_base)^0.5
                               × (num_bands / num_bands_base)^0.25
t_gate_proxy     = lambda_total / delta_e
qubits_proxy     = num_bits_state + num_bits_rot
score            = t_gate_proxy × (1 + qubits_proxy / 100)
```

**Baseline (Si-like):** λ_base = 315.8 Ha, δε = 1×10⁻³ Ha, n_b = 16,
E_cut = 520 eV, N_PW = 1849.  Baseline composite score = 413,698.

**Key findings:**

| Parameter | Tornado impact | Relative impact | Local elasticity |
| --- | --- | --- | --- |
| δε (energy precision) | 628,442 | 151.9 % | −1.01 |
| E_cut (cutoff energy) | 84,938 | 20.5 % | +0.50 |
| n_b (number of bands) | 72,843 | 17.6 % | +0.25 |

Energy precision dominates (~7.4× the cutoff impact); its near-unit inverse
elasticity (≈ −1) confirms direct proportionality between T-gate cost and
1/δε. Cutoff and band count exert sublinear, partially correlated effects.

**Output files produced:**

| File | Description |
| --- | --- |
| `examples/outputs/sensitivity_grid.csv` | Full OFAT sweep (12 rows × 9 columns) |
| `examples/outputs/sensitivity_grid.json` | Same records + baseline, assumptions metadata |
| `examples/outputs/sensitivity_tornado.csv` | Impact summary per parameter (3 rows) |
| `examples/outputs/sensitivity_elasticity.csv` | Local elasticity at baseline (3 rows) |
| `examples/outputs/sensitivity_tornado.png` | Horizontal tornado chart (publication-quality PNG) |
| `examples/sensitivity_methods_note.md` | Proposal-ready 1-page methods narrative |

---

## notebooks/qmatbridge_quickstart.ipynb

**What it demonstrates:**

A user-friendly notebook workflow that combines the ranking and Pareto examples
into one guided analysis.

The notebook will:

- generate missing CSV artifacts automatically by running example scripts
- load ranked candidates with pandas
- render a composite-score bar chart
- render a Pareto frontier scatter plot
- print a short decision summary for first benchmark selection

**Open in Jupyter/VS Code and run cells top to bottom.**

**Input files used:**

| File | Purpose |
| --- | --- |
| `examples/outputs/material_ranking.csv` | Composite-score ranking data |
| `examples/outputs/pareto_candidates.csv` | Pareto membership and objective data |

---

## notebooks/qmatbridge_tour.ipynb

**What it demonstrates:**

A tour of the library that complements the quickstart. Run offline from a checkout
(no API key); one switch (`LIVE`) turns on real OPTIMADE requests.

The notebook will:

- list the installed adapters and exporters from the plugin registry
- draw the unit cells recorded in the Tier-1 entries
- add valence charges (schema 0.3) and run the electron-count check
- run the OPTIMADE and OQMD adapters on recorded-shape responses and compare
  three descriptions of silicon (cell volume, plane-wave count against cutoff)
- export an entry with `numpy_planewave`, then plot the plane-wave set, the
  `N(E)` curve and the ionic structure factor
- round-trip the entry, with its export record, through JSON

Needs `matplotlib` and `numpy` in addition to qmatbridge. The test
`tests/unit/test_tour_notebook.py` executes every code cell.

---

## silicon_entry.json

Committed regression fixture generated by `minimal_entry.py`.  Regenerate at
any time by running the example.

The JSON structure mirrors the schema class hierarchy exactly:

```
{
  "reference": {
    "provenance": { "primary": {...}, "functional": "PBE", ... },
    "structure":  { "formula_reduced": "Si", "lattice": {...}, ... }
  },
  "hamiltonian": {
    "num_electrons": 8,
    "basis":  { "type": "plane_wave", "cutoff_energy_ev": 520.0, ... },
    "terms":  [ {"name": "kinetic", ...}, ... ],
    "oracle": { "method": "lcu", "lambda_total": 315.8, ... }
  },
  "tags": ["silicon", "plane_wave", "benchmark", "lcu"],
  "schema_version": "0.1"
}
```
