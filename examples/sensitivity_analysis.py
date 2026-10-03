"""One-factor-at-a-time sensitivity analysis for first-quantized resource estimates.

Research question:
    Which input control (plane-wave cutoff energy, energy precision target,
    or number of bands) most strongly affects estimated simulation resource
    cost for a silicon-like benchmark material?

Baseline material (Si-like, aligned with minimal_entry.py and pareto_frontier.py):
    lambda_total_base = 315.8  Ha
    delta_e_base      = 1e-3   Ha
    num_bands_base    = 16
    cutoff_ev_base    = 520.0  eV
    num_plane_waves_base = 1849

Proxy models (explicitly documented; not final physics):
    num_plane_waves  = num_plane_waves_base × (cutoff_ev / cutoff_ev_base)^1.5
    num_bits_state   = ceil(log2(num_plane_waves))          [plane-wave register]
    num_bits_rot     = ceil(-log2(delta_e)) + 10            [rotation synthesis register]
    lambda_total     = lambda_total_base
                         × (cutoff_ev / cutoff_ev_base)^0.5
                         × (num_bands / num_bands_base)^0.25
    t_gate_proxy     = lambda_total / delta_e
    qubits_proxy     = num_bits_state + num_bits_rot
    score            = t_gate_proxy × (1 + qubits_proxy / 100)

All formulas are planning proxies, not production resource estimates.
No hidden constants; every formula is encoded in compute_proxies().

Outputs (all written to examples/):
    sensitivity_grid.csv        -- full OFAT sweep records
    sensitivity_grid.json       -- same records + assumptions metadata
    sensitivity_tornado.csv     -- parameter impact summary
    sensitivity_elasticity.csv  -- local elasticity at baseline
    sensitivity_tornado.png     -- horizontal tornado chart

Run from repo root:
    python examples/sensitivity_analysis.py
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Baseline parameters (Si-like mocked material)
# ---------------------------------------------------------------------------

BASELINE: dict[str, float] = {
    "lambda_total_base": 315.8,   # Ha — LCU 1-norm at baseline conditions
    "delta_e": 1e-3,              # Ha — energy precision target
    "num_bands": 16,              # number of bands/orbitals
    "cutoff_ev": 520.0,           # eV — plane-wave kinetic-energy cutoff
    "num_plane_waves_base": 1849, # plane waves at baseline cutoff
}

# One-factor-at-a-time sweep ranges (all other parameters held at baseline)
SWEEPS: dict[str, list[float]] = {
    "cutoff_ev": [400.0, 450.0, 500.0, 550.0, 600.0],
    "delta_e":   [5e-4, 1e-3, 2e-3],
    "num_bands": [12.0, 16.0, 20.0, 24.0],
}

# Explicit model assumptions (saved in JSON metadata)
ASSUMPTIONS: dict[str, str] = {
    "plane_wave_scaling":
        "num_plane_waves = num_plane_waves_base × (cutoff_ev / cutoff_ev_base)^1.5 "
        "[3D free-electron scaling; N ∝ E_cut^(3/2) in reciprocal space volume]",
    "num_bits_state":
        "num_bits_state = ceil(log2(num_plane_waves)) "
        "[minimum qubit register to address all plane-wave basis states]",
    "num_bits_rot":
        "num_bits_rot = ceil(-log2(delta_e)) + 10 "
        "[rotation-synthesis register sized for target precision; +10 is a "
        "fixed overhead representative of standard Solovay-Kitaev circuits]",
    "lambda_scaling":
        "lambda_total = lambda_total_base × (cutoff_ev / cutoff_ev_base)^0.5 "
        "× (num_bands / num_bands_base)^0.25 "
        "[placeholder power-law scaling; exponents are planning estimates, "
        "not derived from first principles for this material]",
    "t_gate_proxy":
        "t_gate_proxy = lambda_total / delta_e "
        "[dominant scaling from qubitized QPE Toffoli count: O(λ/ε)]",
    "qubits_proxy":
        "qubits_proxy = num_bits_state + num_bits_rot "
        "[sum of two dominant qubit registers; ancilla and control qubits omitted]",
    "score":
        "score = t_gate_proxy × (1 + qubits_proxy / 100) "
        "[scalar aggregate weighting T-gates by qubit overhead; "
        "weights are arbitrary and for ranking only]",
    "model_status":
        "All proxy formulas are planning tools for benchmark selection. "
        "They do not constitute a validated resource estimate for any specific material. "
        "Final estimates require material-specific λ calculations (e.g., "
        "Babbush et al. 2019; Lee et al. 2021).",
}


# ---------------------------------------------------------------------------
# Core proxy computation
# ---------------------------------------------------------------------------

def compute_proxies(
    *,
    cutoff_ev: float,
    delta_e: float,
    num_bands: float,
) -> dict[str, float]:
    """Compute all proxy metrics for one parameter combination.

    All formulas are documented in the module docstring and ASSUMPTIONS dict.

    Parameters
    ----------
    cutoff_ev:  Plane-wave kinetic-energy cutoff in eV.
    delta_e:    Energy precision target in Hartree.
    num_bands:  Number of bands/orbitals.

    Returns
    -------
    dict with keys: num_plane_waves, num_bits_state, num_bits_rot,
                    lambda_total, t_gate_proxy, qubits_proxy, score
    """
    cutoff_ev_base    = BASELINE["cutoff_ev"]
    num_pw_base       = BASELINE["num_plane_waves_base"]
    lambda_total_base = BASELINE["lambda_total_base"]
    num_bands_base    = BASELINE["num_bands"]

    # Plane-wave count scales as E_cut^(3/2) in 3D reciprocal space
    num_plane_waves = num_pw_base * (cutoff_ev / cutoff_ev_base) ** 1.5

    # State register: ceil(log2(N)) qubits address N plane-wave states
    num_bits_state = math.ceil(math.log2(num_plane_waves))

    # Rotation register sized for target precision, +10 fixed overhead
    num_bits_rot = math.ceil(-math.log2(delta_e)) + 10

    # λ scaling: placeholder power-law in cutoff and band count
    lambda_total = (
        lambda_total_base
        * (cutoff_ev / cutoff_ev_base) ** 0.5
        * (num_bands / num_bands_base) ** 0.25
    )

    # Resource proxies
    t_gate_proxy  = lambda_total / delta_e
    qubits_proxy  = num_bits_state + num_bits_rot
    score         = t_gate_proxy * (1.0 + qubits_proxy / 100.0)

    return {
        "num_plane_waves": num_plane_waves,
        "num_bits_state":  num_bits_state,
        "num_bits_rot":    num_bits_rot,
        "lambda_total":    lambda_total,
        "t_gate_proxy":    t_gate_proxy,
        "qubits_proxy":    qubits_proxy,
        "score":           score,
    }


# ---------------------------------------------------------------------------
# Baseline computation (reference point for elasticity and tornado)
# ---------------------------------------------------------------------------

BASELINE_PROXIES = compute_proxies(
    cutoff_ev=BASELINE["cutoff_ev"],
    delta_e=BASELINE["delta_e"],
    num_bands=BASELINE["num_bands"],
)

BASELINE_SCORE = BASELINE_PROXIES["score"]


# ---------------------------------------------------------------------------
# OFAT sweep: build sensitivity grid
# ---------------------------------------------------------------------------

def build_sensitivity_grid() -> list[dict[str, Any]]:
    """Run one-factor-at-a-time sweeps.

    For each parameter and each of its sweep values, all other parameters
    are held at their baseline values.

    Returns list of dicts, one per (parameter, value) combination.
    """
    rows: list[dict[str, Any]] = []

    for param_name, values in SWEEPS.items():
        for val in values:
            # Build keyword arguments: start from baseline, override one param
            kwargs: dict[str, float] = {
                "cutoff_ev": BASELINE["cutoff_ev"],
                "delta_e":   BASELINE["delta_e"],
                "num_bands": BASELINE["num_bands"],
            }
            kwargs[param_name] = val

            proxies = compute_proxies(**kwargs)

            rows.append({
                "parameter_name":  param_name,
                "parameter_value": val,
                "cutoff_ev":       kwargs["cutoff_ev"],
                "delta_e":         kwargs["delta_e"],
                "num_bands":       kwargs["num_bands"],
                "lambda_total":    round(proxies["lambda_total"], 4),
                "t_gate_proxy":    round(proxies["t_gate_proxy"], 2),
                "qubits_proxy":    proxies["qubits_proxy"],
                "score":           round(proxies["score"], 2),
            })

    return rows


# ---------------------------------------------------------------------------
# Tornado: parameter impact summary
# ---------------------------------------------------------------------------

def build_tornado(grid: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute min/max score and impact for each parameter.

    Returns rows sorted by absolute_impact descending (deterministic).
    """
    # Group by parameter
    by_param: dict[str, list[dict[str, Any]]] = {}
    for row in grid:
        by_param.setdefault(row["parameter_name"], []).append(row)

    tornado_rows: list[dict[str, Any]] = []
    for param_name, rows in by_param.items():
        scores = [r["score"] for r in rows]
        values = [r["parameter_value"] for r in rows]

        min_idx = scores.index(min(scores))
        max_idx = scores.index(max(scores))

        score_low  = round(min(scores), 2)
        score_high = round(max(scores), 2)
        low_setting  = values[min_idx]
        high_setting = values[max_idx]
        abs_impact  = round(score_high - score_low, 2)
        rel_impact  = round(abs_impact / BASELINE_SCORE * 100.0, 4)

        tornado_rows.append({
            "parameter_name":          param_name,
            "low_setting":             low_setting,
            "high_setting":            high_setting,
            "score_low":               score_low,
            "score_high":              score_high,
            "absolute_impact":         abs_impact,
            "relative_impact_percent": rel_impact,
        })

    # Deterministic sort: descending absolute_impact, then by name for ties
    tornado_rows.sort(key=lambda r: (-r["absolute_impact"], r["parameter_name"]))
    return tornado_rows


# ---------------------------------------------------------------------------
# Elasticity: local sensitivity at baseline
# ---------------------------------------------------------------------------

def build_elasticity() -> list[dict[str, Any]]:
    """Compute local arc elasticity of score w.r.t. each sweep parameter.

    Uses the two sweep values immediately adjacent to the baseline value
    (or the closest available pair) for a centered finite difference.

    Elasticity = (ΔScore/Score_baseline) / (ΔParam/Param_baseline)
    """
    elasticity_rows: list[dict[str, Any]] = []

    param_baselines = {
        "cutoff_ev": BASELINE["cutoff_ev"],
        "delta_e":   BASELINE["delta_e"],
        "num_bands": BASELINE["num_bands"],
    }

    for param_name, values in SWEEPS.items():
        base_val = param_baselines[param_name]
        sorted_vals = sorted(values)

        # Find the two values bracketing or closest to the baseline
        below = [v for v in sorted_vals if v <= base_val]
        above = [v for v in sorted_vals if v >= base_val]

        if not below or not above:
            # Use min/max of the sweep range
            v_lo, v_hi = sorted_vals[0], sorted_vals[-1]
        else:
            v_lo = max(below)  # closest below-or-equal
            v_hi = min(above)  # closest above-or-equal

        # Avoid zero interval (handles case where baseline is exactly a sweep value)
        if v_lo == v_hi:
            # Use immediate neighbors
            idx = sorted_vals.index(v_lo)
            if idx == 0:
                v_lo, v_hi = sorted_vals[0], sorted_vals[1]
            elif idx == len(sorted_vals) - 1:
                v_lo, v_hi = sorted_vals[-2], sorted_vals[-1]
            else:
                v_lo, v_hi = sorted_vals[idx - 1], sorted_vals[idx + 1]

        kwargs_lo: dict[str, float] = {
            "cutoff_ev": BASELINE["cutoff_ev"],
            "delta_e":   BASELINE["delta_e"],
            "num_bands": BASELINE["num_bands"],
        }
        kwargs_hi = dict(kwargs_lo)
        kwargs_lo[param_name] = v_lo
        kwargs_hi[param_name] = v_hi

        score_lo = compute_proxies(**kwargs_lo)["score"]
        score_hi = compute_proxies(**kwargs_hi)["score"]

        d_score = score_hi - score_lo
        d_param = v_hi - v_lo

        # Normalized (dimensionless) elasticity
        elasticity = (d_score / BASELINE_SCORE) / (d_param / base_val)

        elasticity_rows.append({
            "parameter_name":            param_name,
            "local_elasticity_at_baseline": round(elasticity, 6),
        })

    # Sort by absolute elasticity descending for readability
    elasticity_rows.sort(
        key=lambda r: (-abs(r["local_elasticity_at_baseline"]), r["parameter_name"])
    )
    return elasticity_rows


# ---------------------------------------------------------------------------
# CSV/JSON export utilities
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(obj: Any, path: Path) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Tornado plot
# ---------------------------------------------------------------------------

def plot_tornado(
    tornado: list[dict[str, Any]],
    baseline_score: float,
    out_path: Path,
) -> Path | None:
    """Save a horizontal tornado chart. Returns None if matplotlib unavailable."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.ticker as mticker
    except ImportError:
        return None

    fig, ax = plt.subplots(figsize=(8, max(3, 1.2 * len(tornado) + 1.5)))

    colors_pos = "#2a9d8f"   # teal  — impact above baseline
    colors_neg = "#e76f51"   # coral — impact below baseline

    param_labels = {
        "cutoff_ev": "Cutoff energy\n(eV)",
        "delta_e":   "Energy precision\n(δε, Ha)",
        "num_bands": "Number of bands",
    }

    y_pos = list(range(len(tornado)))

    for i, row in enumerate(tornado):
        lo = row["score_low"]
        hi = row["score_high"]

        # Bar from low to high, centered visual cue at baseline
        ax.barh(
            i,
            hi - baseline_score,
            left=baseline_score,
            height=0.55,
            color=colors_pos,
            alpha=0.85,
        )
        ax.barh(
            i,
            lo - baseline_score,
            left=baseline_score,
            height=0.55,
            color=colors_neg,
            alpha=0.85,
        )

        # Annotate impact magnitude on the right
        ax.text(
            max(hi, baseline_score) + 0.005 * baseline_score,
            i,
            f"±{row['relative_impact_percent']:.1f}%",
            va="center",
            fontsize=9,
            color="#333333",
        )

    ax.axvline(baseline_score, color="#555555", linewidth=1.2, linestyle="--",
               label=f"Baseline score = {baseline_score:,.0f}")

    y_labels = [
        param_labels.get(row["parameter_name"], row["parameter_name"])
        for row in tornado
    ]
    ax.set_yticks(y_pos)
    ax.set_yticklabels(y_labels, fontsize=10)

    ax.set_xlabel("Composite score  (T-gate proxy × qubit overhead factor)", fontsize=10)
    ax.set_title(
        "Sensitivity Tornado: Effect of Input Parameters\non Estimated Simulation Resource Score",
        fontsize=11,
        pad=10,
    )
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.legend(frameon=False, fontsize=9)
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------

def print_summary(
    tornado: list[dict[str, Any]],
    elasticity: list[dict[str, Any]],
    baseline_score: float,
) -> None:
    print("=" * 65)
    print("  Sensitivity Analysis — QMatBridge Si-like Benchmark")
    print("=" * 65)
    print(f"\n  Baseline score : {baseline_score:,.2f}")
    print("  (score = t_gate_proxy × (1 + qubits_proxy/100))\n")

    print("  Tornado ranking (descending absolute impact):")
    print(f"  {'Parameter':<20} {'score_low':>12} {'score_high':>12} "
          f"{'abs_impact':>12} {'rel_%':>8}")
    print("  " + "-" * 68)
    for row in tornado:
        print(
            f"  {row['parameter_name']:<20} "
            f"{row['score_low']:>12,.2f} "
            f"{row['score_high']:>12,.2f} "
            f"{row['absolute_impact']:>12,.2f} "
            f"{row['relative_impact_percent']:>8.2f}%"
        )

    print("\n  Local elasticity at baseline (|elasticity| → sensitivity):")
    print(f"  {'Parameter':<20} {'elasticity':>14}")
    print("  " + "-" * 36)
    for row in elasticity:
        print(f"  {row['parameter_name']:<20} "
              f"{row['local_elasticity_at_baseline']:>14.4f}")
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    out_dir = Path(__file__).parent

    # 1. Build data
    grid        = build_sensitivity_grid()
    tornado     = build_tornado(grid)
    elasticity  = build_elasticity()

    # 2. Assemble JSON artifact (records + assumptions + baseline)
    grid_json_obj = {
        "schema_version": "0.1",
        "example": "sensitivity_analysis",
        "baseline": BASELINE,
        "baseline_proxies": {
            k: round(v, 6) if isinstance(v, float) else v
            for k, v in BASELINE_PROXIES.items()
        },
        "assumptions": ASSUMPTIONS,
        "records": grid,
    }

    # 3. Write outputs
    grid_csv_path        = out_dir / "sensitivity_grid.csv"
    grid_json_path       = out_dir / "sensitivity_grid.json"
    tornado_csv_path     = out_dir / "sensitivity_tornado.csv"
    elasticity_csv_path  = out_dir / "sensitivity_elasticity.csv"
    tornado_png_path     = out_dir / "sensitivity_tornado.png"

    write_csv(grid, grid_csv_path)
    write_json(grid_json_obj, grid_json_path)
    write_csv(tornado, tornado_csv_path)
    write_csv(elasticity, elasticity_csv_path)

    png_written = plot_tornado(tornado, BASELINE_SCORE, tornado_png_path)

    # 4. Console summary
    print_summary(tornado, elasticity, BASELINE_SCORE)

    # 5. Report
    print("  Output files:")
    print(f"    {grid_csv_path}")
    print(f"    {grid_json_path}")
    print(f"    {tornado_csv_path}")
    print(f"    {elasticity_csv_path}")
    if png_written:
        print(f"    {tornado_png_path}")
    else:
        print("    sensitivity_tornado.png  [skipped — matplotlib not available]")

    # 6. Verify row count consistency
    assert len(grid) == sum(len(v) for v in SWEEPS.values()), (
        "Grid row count mismatch: expected one row per (parameter, value) pair"
    )
    assert len(tornado) == len(SWEEPS), (
        "Tornado row count mismatch: expected one row per parameter"
    )
    assert len(elasticity) == len(SWEEPS), (
        "Elasticity row count mismatch: expected one row per parameter"
    )
    print("\n  ✓ Row count assertions passed.")
    print(f"  ✓ Grid: {len(grid)} rows  |  "
          f"Tornado: {len(tornado)} rows  |  "
          f"Elasticity: {len(elasticity)} rows")


if __name__ == "__main__":
    main()
