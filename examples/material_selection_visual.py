"""Material selection example with visual ranking output.

Real problem:
    Given several candidate materials, choose which Hamiltonian to study first
    for fault-tolerant simulation based on a simple resource proxy.

This script builds a few QMatEntry records, computes a cost score from oracle
metadata, and prints:
    1) a ranked comparison table
    2) an ASCII bar chart for quick visual inspection

Run:
    python examples/material_selection_visual.py
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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
class CandidateScore:
    """Scored material candidate for ranking and display."""

    formula: str
    source_id: str
    lambda_total: float
    delta_e: float
    qubits_proxy: int
    t_gate_proxy: float
    score: float


def export_rankings(rows: list[CandidateScore], out_dir: Path) -> tuple[Path, Path]:
    """Write ranking outputs to CSV and JSON for notebook plotting."""
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "material_ranking.csv"
    json_path = out_dir / "material_ranking.json"

    fieldnames = [
        "rank",
        "formula",
        "source_id",
        "lambda_total",
        "delta_e",
        "qubits_proxy",
        "t_gate_proxy",
        "score",
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            writer.writerow(
                {
                    "rank": idx,
                    "formula": row.formula,
                    "source_id": row.source_id,
                    "lambda_total": row.lambda_total,
                    "delta_e": row.delta_e,
                    "qubits_proxy": row.qubits_proxy,
                    "t_gate_proxy": row.t_gate_proxy,
                    "score": row.score,
                }
            )

    payload = [
        {
            "rank": idx,
            "formula": row.formula,
            "source_id": row.source_id,
            "lambda_total": row.lambda_total,
            "delta_e": row.delta_e,
            "qubits_proxy": row.qubits_proxy,
            "t_gate_proxy": row.t_gate_proxy,
            "score": row.score,
        }
        for idx, row in enumerate(rows, start=1)
    ]
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")

    return csv_path, json_path


def export_png_chart(rows: list[CandidateScore], out_dir: Path) -> Path | None:
    """Write a matplotlib PNG ranking chart. Returns None if matplotlib is missing."""
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / "material_ranking.png"

    labels = [f"{row.formula} ({row.source_id})" for row in rows]
    scores = [row.score for row in rows]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.barh(labels, scores, color=["#2a9d8f", "#4c78a8", "#e76f51"])
    ax.invert_yaxis()
    ax.set_title("Material Ranking by Proxy Simulation Cost")
    ax.set_xlabel("Score (lower is better)")
    ax.grid(axis="x", linestyle="--", alpha=0.35)

    for bar, score in zip(bars, scores):
        ax.text(
            bar.get_width() * 1.01,
            bar.get_y() + bar.get_height() / 2,
            f"{score:,.0f}",
            va="center",
            fontsize=9,
        )

    fig.tight_layout()
    fig.savefig(png_path, dpi=160)
    plt.close(fig)
    return png_path


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
    """Build a compact QMatEntry for ranking experiments."""
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


def compute_scores(entries: Iterable[QMatEntry]) -> list[CandidateScore]:
    """Compute ranking metrics from entry oracle data.

    We use a practical proxy objective:
        t_gate_proxy = lambda_total / delta_e
        qubits_proxy = num_bits_state + num_bits_rot
        score = t_gate_proxy * (1 + qubits_proxy / 100)

    Lower score is better.
    """
    scored: list[CandidateScore] = []

    for entry in entries:
        oracle = entry.hamiltonian.oracle
        if oracle is None or oracle.lambda_total is None or oracle.delta_e is None:
            continue

        bits_state = oracle.num_bits_state or 0
        bits_rot = oracle.num_bits_rot or 0
        qubits_proxy = bits_state + bits_rot

        t_gate_proxy = oracle.lambda_total / oracle.delta_e
        score = t_gate_proxy * (1.0 + qubits_proxy / 100.0)

        scored.append(
            CandidateScore(
                formula=entry.reference.structure.formula_reduced,
                source_id=entry.reference.provenance.primary.identifier,
                lambda_total=oracle.lambda_total,
                delta_e=oracle.delta_e,
                qubits_proxy=qubits_proxy,
                t_gate_proxy=t_gate_proxy,
                score=score,
            )
        )

    scored.sort(key=lambda row: row.score)
    return scored


def render_table(rows: list[CandidateScore]) -> str:
    """Return a plain-text table for terminal display."""
    header = (
        "Rank  Material  ID       lambda(Ha)  delta_e(Ha)  "
        "T-gate-proxy   qubits-proxy   score"
    )
    sep = "-" * len(header)

    lines = [header, sep]
    for i, row in enumerate(rows, start=1):
        lines.append(
            f"{i:<5} {row.formula:<9} {row.source_id:<8} "
            f"{row.lambda_total:>10.1f} {row.delta_e:>12.4g} "
            f"{row.t_gate_proxy:>13,.0f} {row.qubits_proxy:>14} "
            f"{row.score:>10,.0f}"
        )
    return "\n".join(lines)


def render_bar_chart(rows: list[CandidateScore], width: int = 42) -> str:
    """Render an ASCII horizontal bar chart for the score values."""
    if not rows:
        return "(no rows to plot)"

    max_score = max(row.score for row in rows)
    lines = ["Visual ranking (shorter bar is better):"]

    for row in rows:
        ratio = row.score / max_score if max_score else 0.0
        bar_len = max(1, int(ratio * width))
        bar = "#" * bar_len
        label = f"{row.formula} ({row.source_id})"
        lines.append(f"{label:<20} |{bar:<{width}}| {row.score:,.0f}")

    return "\n".join(lines)


def main() -> None:
    candidates = [
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
    ]

    rows = compute_scores(candidates)

    print("=== Real Problem: Which Material Should We Simulate First? ===")
    print("Objective: choose the lowest proxy resource cost for first-quantized LCU.")
    print()
    print(render_table(rows))
    print()
    print(render_bar_chart(rows))

    if rows:
        winner = rows[0]
        print()
        print("Recommended first benchmark:")
        print(
            f"  {winner.formula} ({winner.source_id}) with score {winner.score:,.0f}"
        )

    out_dir = Path(__file__).parent
    csv_path, json_path = export_rankings(rows, out_dir)
    png_path = export_png_chart(rows, out_dir)

    print()
    print("Notebook-friendly exports:")
    print(f"  CSV : {csv_path}")
    print(f"  JSON: {json_path}")
    if png_path is None:
        print("  PNG : skipped (matplotlib is not available)")
    else:
        print(f"  PNG : {png_path}")


if __name__ == "__main__":
    main()
