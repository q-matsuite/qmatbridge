"""Pareto frontier example for benchmark candidate selection.

Real problem:
    Select benchmark materials under two competing objectives:
    1) lower estimated T-gate proxy cost
    2) lower qubit proxy usage

This script:
    - builds several QMatEntry candidates
    - computes objective values
    - identifies the non-dominated (Pareto-optimal) set
    - prints a ranked summary
    - exports CSV/JSON for notebooks
    - saves a matplotlib scatter plot with the Pareto frontier

Run:
    python examples/pareto_frontier.py
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from qmatbridge.schema import (
    BasisMetadata,
    ExternalIdentifier,
    HamiltonianMetadata,
    LatticeMetadata,
    MaterialReference,
    OracleMetadata,
    QMatEntry,
    SourceProvenance,
    StructureMetadata,
)


@dataclass
class Candidate:
    """Candidate material with computed optimization objectives."""

    formula: str
    source_id: str
    t_gate_proxy: float
    qubits_proxy: int


def make_entry(
    *,
    identifier: str,
    formula_reduced: str,
    formula_unit_cell: str,
    num_sites: int,
    num_electrons: int,
    num_bands: int,
    cutoff_ev: float,
    num_plane_waves: int,
    lambda_total: float,
    delta_e: float,
    num_bits_state: int,
    num_bits_rot: int,
) -> QMatEntry:
    """Build a compact QMatEntry candidate."""
    reference = MaterialReference(
        provenance=SourceProvenance(
            primary=ExternalIdentifier(
                source="materials_project",
                identifier=identifier,
                url=f"https://materialsproject.org/materials/{identifier}",
            ),
            functional="PBE",
            pseudopotential="PAW_PBE",
            code="VASP",
        ),
        structure=StructureMetadata(
            formula_reduced=formula_reduced,
            formula_unit_cell=formula_unit_cell,
            num_sites=num_sites,
            species=[formula_reduced] * num_sites,
            lattice=LatticeMetadata(
                a=4.0,
                b=4.0,
                c=4.0,
                alpha=90.0,
                beta=90.0,
                gamma=90.0,
            ),
        ),
    )

    oracle = OracleMetadata(
        method="lcu",
        lambda_total=lambda_total,
        delta_e=delta_e,
        num_bits_state=num_bits_state,
        num_bits_rot=num_bits_rot,
    )

    hamiltonian = HamiltonianMetadata(
        num_electrons=num_electrons,
        spin_polarized=False,
        basis=BasisMetadata(
            type="plane_wave",
            cutoff_energy_ev=cutoff_ev,
            num_plane_waves=num_plane_waves,
        ),
        num_bands=num_bands,
        oracle=oracle,
    )

    return QMatEntry(reference=reference, hamiltonian=hamiltonian)


def to_candidate(entry: QMatEntry) -> Candidate:
    """Extract objective values from a QMatEntry."""
    oracle = entry.hamiltonian.oracle
    if oracle is None or oracle.lambda_total is None or oracle.delta_e is None:
        raise ValueError("oracle.lambda_total and oracle.delta_e are required")

    t_gate_proxy = oracle.lambda_total / oracle.delta_e
    qubits_proxy = (oracle.num_bits_state or 0) + (oracle.num_bits_rot or 0)

    return Candidate(
        formula=entry.reference.structure.formula_reduced,
        source_id=entry.reference.provenance.primary.identifier,
        t_gate_proxy=t_gate_proxy,
        qubits_proxy=qubits_proxy,
    )


def dominates(a: Candidate, b: Candidate) -> bool:
    """Return True if candidate a Pareto-dominates candidate b.

    Objective: minimize both t_gate_proxy and qubits_proxy.
    """
    better_or_equal = (
        a.t_gate_proxy <= b.t_gate_proxy and a.qubits_proxy <= b.qubits_proxy
    )
    strictly_better = (
        a.t_gate_proxy < b.t_gate_proxy or a.qubits_proxy < b.qubits_proxy
    )
    return better_or_equal and strictly_better


def pareto_frontier(candidates: list[Candidate]) -> list[Candidate]:
    """Compute the non-dominated set for two-objective minimization."""
    frontier: list[Candidate] = []

    for candidate in candidates:
        is_dominated = any(
            dominates(other, candidate)
            for other in candidates
            if other is not candidate
        )
        if not is_dominated:
            frontier.append(candidate)

    frontier.sort(key=lambda c: (c.t_gate_proxy, c.qubits_proxy))
    return frontier


def export_results(
    candidates: list[Candidate], frontier: list[Candidate], out_dir: Path
) -> tuple[Path, Path]:
    """Export all candidates and Pareto membership to CSV and JSON."""
    out_dir.mkdir(parents=True, exist_ok=True)

    frontier_keys = {(c.formula, c.source_id) for c in frontier}
    rows = []
    for c in sorted(candidates, key=lambda x: (x.t_gate_proxy, x.qubits_proxy)):
        rows.append(
            {
                "formula": c.formula,
                "source_id": c.source_id,
                "t_gate_proxy": c.t_gate_proxy,
                "qubits_proxy": c.qubits_proxy,
                "is_pareto_optimal": (c.formula, c.source_id) in frontier_keys,
            }
        )

    csv_path = out_dir / "pareto_candidates.csv"
    json_path = out_dir / "pareto_candidates.json"

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
        fh.write("\n")

    return csv_path, json_path


def export_plot(
    candidates: list[Candidate], frontier: list[Candidate], out_dir: Path
) -> Path | None:
    """Save a matplotlib scatter plot and frontier line. Returns None if unavailable."""
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / "pareto_frontier.png"

    fig, ax = plt.subplots(figsize=(8, 5))

    frontier_keys = {(c.formula, c.source_id) for c in frontier}
    dominated = [
        c for c in candidates if (c.formula, c.source_id) not in frontier_keys
    ]

    if dominated:
        ax.scatter(
            [c.qubits_proxy for c in dominated],
            [c.t_gate_proxy for c in dominated],
            label="Dominated",
            color="#9aa0a6",
            s=55,
            alpha=0.8,
        )

    ax.scatter(
        [c.qubits_proxy for c in frontier],
        [c.t_gate_proxy for c in frontier],
        label="Pareto-optimal",
        color="#2a9d8f",
        edgecolors="#1b4332",
        linewidths=0.8,
        s=85,
        zorder=3,
    )

    if len(frontier) >= 2:
        frontier_sorted = sorted(frontier, key=lambda c: c.qubits_proxy)
        ax.plot(
            [c.qubits_proxy for c in frontier_sorted],
            [c.t_gate_proxy for c in frontier_sorted],
            color="#2a9d8f",
            linestyle="--",
            linewidth=1.3,
            zorder=2,
        )

    for c in candidates:
        ax.annotate(
            c.formula,
            (c.qubits_proxy, c.t_gate_proxy),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )

    ax.set_title("Pareto Frontier: T-gate Proxy vs Qubit Proxy")
    ax.set_xlabel("Qubit proxy (lower is better)")
    ax.set_ylabel("T-gate proxy (lower is better)")
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(png_path, dpi=170)
    plt.close(fig)

    return png_path


def render_table(candidates: list[Candidate], frontier: list[Candidate]) -> str:
    """Render a summary table with Pareto membership."""
    frontier_keys = {(c.formula, c.source_id) for c in frontier}

    header = (
        "Material  ID       qubits_proxy   t_gate_proxy   pareto_optimal"
    )
    sep = "-" * len(header)
    lines = [header, sep]

    for c in sorted(candidates, key=lambda x: (x.t_gate_proxy, x.qubits_proxy)):
        flag = "yes" if (c.formula, c.source_id) in frontier_keys else "no"
        lines.append(
            f"{c.formula:<9} {c.source_id:<8} {c.qubits_proxy:>12} "
            f"{c.t_gate_proxy:>14,.0f} {flag:>16}"
        )

    return "\n".join(lines)


def main() -> None:
    entries = [
        make_entry(
            identifier="mp-149",
            formula_reduced="Si",
            formula_unit_cell="Si2",
            num_sites=2,
            num_electrons=8,
            num_bands=16,
            cutoff_ev=520.0,
            num_plane_waves=1849,
            lambda_total=315.8,
            delta_e=1.0e-3,
            num_bits_state=11,
            num_bits_rot=20,
        ),
        make_entry(
            identifier="mp-66",
            formula_reduced="LiH",
            formula_unit_cell="Li1H1",
            num_sites=2,
            num_electrons=4,
            num_bands=10,
            cutoff_ev=450.0,
            num_plane_waves=1320,
            lambda_total=140.0,
            delta_e=1.0e-3,
            num_bits_state=11,
            num_bits_rot=18,
        ),
        make_entry(
            identifier="mp-1265",
            formula_reduced="MgO",
            formula_unit_cell="Mg1O1",
            num_sites=2,
            num_electrons=10,
            num_bands=20,
            cutoff_ev=600.0,
            num_plane_waves=2560,
            lambda_total=410.0,
            delta_e=1.0e-3,
            num_bits_state=12,
            num_bits_rot=22,
        ),
        make_entry(
            identifier="mp-1902",
            formula_reduced="AlN",
            formula_unit_cell="Al1N1",
            num_sites=2,
            num_electrons=8,
            num_bands=18,
            cutoff_ev=540.0,
            num_plane_waves=2100,
            lambda_total=260.0,
            delta_e=1.0e-3,
            num_bits_state=10,
            num_bits_rot=18,
        ),
        make_entry(
            identifier="mp-22862",
            formula_reduced="GaN",
            formula_unit_cell="Ga1N1",
            num_sites=2,
            num_electrons=18,
            num_bands=26,
            cutoff_ev=620.0,
            num_plane_waves=2750,
            lambda_total=380.0,
            delta_e=1.0e-3,
            num_bits_state=9,
            num_bits_rot=16,
        ),
    ]

    candidates = [to_candidate(entry) for entry in entries]
    frontier = pareto_frontier(candidates)

    print("=== Pareto Frontier for Benchmark Selection ===")
    print("Objectives: minimize qubits_proxy and t_gate_proxy simultaneously")
    print()
    print(render_table(candidates, frontier))

    print("\nPareto-optimal set:")
    for item in frontier:
        print(
            f"  - {item.formula} ({item.source_id}): "
            f"qubits={item.qubits_proxy}, t-gate={item.t_gate_proxy:,.0f}"
        )

    out_dir = Path(__file__).parent
    csv_path, json_path = export_results(candidates, frontier, out_dir)
    png_path = export_plot(candidates, frontier, out_dir)

    print("\nExports:")
    print(f"  CSV : {csv_path}")
    print(f"  JSON: {json_path}")
    if png_path is None:
        print("  PNG : skipped (matplotlib is not available)")
    else:
        print(f"  PNG : {png_path}")


if __name__ == "__main__":
    main()
