# Sensitivity Analysis: Methods Note

**Example:** `sensitivity_analysis.py`  
**QMatBridge version:** 0.1  
**Date:** 2026-06-04

---

## Research Question

Which input control — plane-wave cutoff energy (E_cut), energy precision
target (δε), or number of bands (n_b) — most strongly affects the estimated
simulation resource cost for a benchmark material representative of bulk
silicon?

---

## Baseline Material

A silicon-like mocked material aligned with the `minimal_entry.py` and
`pareto_frontier.py` examples serves as the reference configuration:

| Parameter | Symbol | Baseline value |
|---|---|---|
| LCU 1-norm | λ_base | 315.8 Ha |
| Energy precision | δε_base | 1 × 10⁻³ Ha |
| Number of bands | n_b,base | 16 |
| Plane-wave cutoff | E_cut,base | 520.0 eV |
| Plane-wave count | N_PW,base | 1 849 |

---

## Sensitivity Methodology

A one-factor-at-a-time (OFAT) sweep was applied: for each input parameter,
a discrete range of values was evaluated while holding all other parameters
at their baseline values. The sweep ranges were:

- E_cut ∈ {400, 450, 500, 550, 600} eV
- δε ∈ {5 × 10⁻⁴, 1 × 10⁻³, 2 × 10⁻³} Ha
- n_b ∈ {12, 16, 20, 24}

---

## Proxy Models

All formulas are planning proxies, not production resource estimates.
No constants are hidden; every formula is encoded verbatim in
`compute_proxies()` in the script and recorded in `sensitivity_grid.json`.

**Plane-wave count** (3D reciprocal-space volume scaling):

    N_PW = N_PW,base × (E_cut / E_cut,base)^1.5

**State register** (minimum qubits to address N_PW basis states):

    num_bits_state = ⌈log₂(N_PW)⌉

**Rotation register** (precision-limited synthesis register):

    num_bits_rot = ⌈−log₂(δε)⌉ + 10

The additive constant (+10) represents a fixed overhead typical of
Solovay-Kitaev rotation synthesis circuits and is treated as invariant
across this sweep.

**LCU 1-norm scaling** (placeholder power-law; exponents are planning
estimates, not material-specific derivations):

    λ = λ_base × (E_cut / E_cut,base)^0.5 × (n_b / n_b,base)^0.25

**T-gate proxy** (dominant scaling from qubitized QPE):

    t_gate_proxy = λ / δε

**Qubit proxy** (two dominant registers only; ancilla omitted):

    qubits_proxy = num_bits_state + num_bits_rot

**Composite score** (scalar aggregate for ranking; weights are arbitrary):

    score = t_gate_proxy × (1 + qubits_proxy / 100)

---

## Metrics and Outputs

Three summary statistics are computed from the OFAT grid:

1. **Tornado impact** (`sensitivity_tornado.csv`): for each parameter, the
   absolute score range (max − min over its sweep) and the relative impact
   expressed as a percentage of the baseline score. Parameters are ranked
   by absolute impact.

2. **Local elasticity** (`sensitivity_elasticity.csv`): a dimensionless arc
   elasticity evaluated near the baseline using the two adjacent sweep
   points:

       elasticity = (ΔScore / Score_base) / (ΔParam / Param_base)

   |elasticity| > 1 indicates elastic (super-proportional) sensitivity;
   |elasticity| < 1 indicates inelastic sensitivity.

3. **Full OFAT grid** (`sensitivity_grid.csv`, `sensitivity_grid.json`):
   one record per (parameter, sweep value) with all intermediate quantities
   (λ, t_gate_proxy, qubits_proxy, score) for downstream analysis.

---

## Key Findings

| Parameter | Tornado impact | Relative impact | Local elasticity |
|---|---|---|---|
| δε (energy precision) | 628,442 | 151.9 % | −1.01 |
| E_cut (cutoff energy) | 84,938 | 20.5 % | +0.50 |
| n_b (number of bands) | 72,843 | 17.6 % | +0.25 |

The energy precision target δε is the dominant control by a wide margin
(~7.4× the impact of E_cut). Its elasticity of −1.01 confirms near-unit
inverse proportionality: halving δε approximately doubles the composite
score. The cutoff energy and band count exert sublinear, partially
correlated effects through the λ scaling, with elasticities of +0.50 and
+0.25 respectively.

---

## Interpretation Guidance

The tornado ranking directly informs benchmark planning priorities. Because
δε dominates, efforts to reduce estimated resource cost should first focus
on relaxing the precision target where scientifically defensible (e.g.,
targeting chemical accuracy ≈ 1 kcal/mol ≈ 1.6 × 10⁻³ Ha rather than
spectroscopic accuracy). Cutoff energy and band count have roughly comparable
and sublinear influence; their combined impact (~38% relative) warrants
attention only after the precision target is fixed.

The elasticity values serve as leading-order sensitivity indicators for
multi-variable optimization and can be used directly in gradient-free
parameter screening.

---

## Limitations

1. **OFAT, not joint sensitivity.** Interaction effects between parameters
   are not captured. A full factorial or variance-based (Sobol) analysis
   would be required for coupled sensitivity estimates.

2. **Placeholder power-law scaling.** The λ scaling exponents (0.5 for
   E_cut, 0.25 for n_b) are planning estimates derived from dimensional
   arguments, not from material-specific electronic-structure calculations.
   They should be replaced with empirical fits or exact expressions once
   real data are available.

3. **Two-register qubit model.** The qubit proxy omits ancilla, control,
   and QROM registers. Full resource estimates would increase qubit counts
   by a factor of approximately 2–5 depending on the circuit architecture.

4. **Fixed rotation overhead.** The +10 constant in num_bits_rot is a
   representative approximation. Its value can range from 0 to ≳20
   depending on the rotation synthesis algorithm and target gate set.

5. **Mocked material.** All numerical values are derived from a synthetic
   Si-like baseline. Results are not quantitatively transferable to
   other materials without re-parameterizing λ_base, N_PW,base, and the
   scaling exponents.

---

## Reproducibility

All outputs are deterministic: no random sampling is involved. Re-running
`python examples/sensitivity_analysis.py` from the repository root
regenerates all five output files with identical numerical content.
The JSON artifact (`sensitivity_grid.json`) records all assumptions and
baseline values required to reconstruct the computation independently.
