# QMatBridge Benchmarks

This directory holds benchmark scripts and data that validate and characterize
the Hamiltonians produced by QMatBridge.

---

## Philosophy

Benchmarks here serve two purposes:

1. **Correctness validation** — confirm that exported Hamiltonians match
   reference values from the literature or authoritative DFT codes.
2. **Resource characterization** — measure the quantities that gate
   fault-tolerant cost estimates: LCU 1-norm (λ), number of plane-wave
   basis functions (N), and electron count (η).

---

## Planned Benchmark Suite

### Tier 1 — Core materials (open-access, well-studied)

| Material | mp-id | Cell | Valence electrons | Notes |
|----------|-------|------|-------------------|-------|
| Si (diamond) | mp-149 | Si₂ | 8 | Canonical test case |
| LiH | mp-23703 | LiH | 4 | Small system, exact-diag reference |
| Fe (BCC) | mp-13 | Fe | 14 | Magnetic, spin-polarized |
| MgO | mp-1265 | MgO | 14 | Ionic, wide gap |
| TiO₂ (rutile) | mp-2657 | Ti₂O₄ | 44 | d-electron system |

Electron counts are derived from the default Materials Project VASP POTCAR
valences (`Si`, `Li_sv`, `H`, `Fe_pv`, `Mg_pv`, `O`, `Ti_pv`) for the
primitive cell; see [`tier1.py`](tier1.py).  The plane-wave cutoff is whatever
the MP static calculation used (520 eV for the standard MP workflow).

**Fixtures.** `python benchmarks/build_tier1_fixtures.py` (needs `MP_API_KEY`
and the `[mp]` extra) fetches each material, checks it against the spec —
species, electron count, spin — and writes `benchmarks/fixtures/<key>.json`
only if everything matches.  MP IDs are verified at that point; any
mismatch is reported rather than written.

### Tier 2 — Resource estimation targets

Materials from published fault-tolerant cost estimates
(Babbush et al. 2019, Su et al. 2021, Berry et al. 2023) to allow
direct comparison with reported λ and qubit counts.

---

## Running Benchmarks

```bash
pip install -e ".[dev,mp]"
pytest benchmarks/ -v --tb=short
```

Individual scripts can also be run directly:

```bash
python benchmarks/lcu_norm_silicon.py
```

---

## Adding a Benchmark

1. Create `benchmarks/<name>.py` with a `run()` function returning a dict of metrics.
2. Add a corresponding `tests/test_benchmark_<name>.py` that asserts on the metrics.
3. Add the material to the table above.
4. Ensure all reference data is derived from open-access sources.
