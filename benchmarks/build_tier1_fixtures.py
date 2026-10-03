"""Generate Tier-1 benchmark fixtures from the live Materials Project API.

Usage::

    export MP_API_KEY=...
    pip install -e ".[mp]"
    python benchmarks/build_tier1_fixtures.py [--out benchmarks/fixtures]

Each fixture is validated against :data:`benchmarks.tier1.TIER1` (species,
site count, electron count, spin) before being written; mismatches are
reported and no file is written for that material.  Review the diff and
commit the resulting JSON — it is the reference input for downstream
regression tests.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benchmarks.tier1 import TIER1, BenchmarkSpec
from qmatbridge.adapters.materials_project import fetch_entry_from_mp
from qmatbridge.io import write_entry_json
from qmatbridge.schema import QMatEntry


def check_entry(spec: BenchmarkSpec, entry: QMatEntry) -> list[str]:
    """Return a list of mismatches between *entry* and *spec* (empty if OK)."""
    problems: list[str] = []
    species = sorted(entry.reference.structure.species)
    if species != sorted(spec.cell_species):
        problems.append(f"species {species} != expected {sorted(spec.cell_species)}")
    if entry.hamiltonian.num_electrons != spec.expected_electrons:
        problems.append(
            f"electrons {entry.hamiltonian.num_electrons} "
            f"!= expected {spec.expected_electrons}"
        )
    if entry.hamiltonian.spin_polarized != spec.spin_polarized:
        problems.append(
            f"spin_polarized {entry.hamiltonian.spin_polarized} "
            f"!= expected {spec.spin_polarized}"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "fixtures")
    args = ap.parse_args(argv)

    failures = 0
    for spec in TIER1:
        entry = fetch_entry_from_mp(spec.mp_id, tags=["benchmark", "tier1", spec.key])
        problems = check_entry(spec, entry)
        if problems:
            failures += 1
            print(f"[FAIL] {spec.key} ({spec.mp_id}): " + "; ".join(problems))
            continue
        path = write_entry_json(entry, args.out / spec.fixture_name)
        print(f"[ ok ] {spec.key} ({spec.mp_id}) -> {path}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
