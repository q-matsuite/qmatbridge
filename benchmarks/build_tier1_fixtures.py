"""Generate Tier-1 benchmark fixtures from the live Materials Project API.

Usage::

    export MP_API_KEY=...
    pip install -e ".[mp]"
    python benchmarks/build_tier1_fixtures.py [--out benchmarks/fixtures]
                                              [--site website/data/examples.json]

Each fixture is validated against :data:`benchmarks.tier1.TIER1` (species,
site count, electron count, spin) before being written; mismatches are
reported and no file is written for that material.  Review the diff and
commit the resulting JSON — it is the reference input for downstream
regression tests.  With ``--site`` the same run also writes the data file the
landing page (``tools/build_site.py``) embeds, including atomic positions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmarks.tier1 import TIER1, BenchmarkSpec
from qmatbridge.adapters.materials_project import (
    MPAdapterConfig,
    _open_client,
    _summary_doc,
    fetch_entry_from_mp,
)
from qmatbridge.io import to_dict, write_entry_json
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


def site_record(spec: BenchmarkSpec, entry: QMatEntry, sites: list[dict]) -> dict:
    """Assemble the per-material record consumed by the landing page."""
    st, lat = entry.reference.structure, entry.reference.structure.lattice
    h = entry.hamiltonian
    return {
        "key": spec.key,
        "label": spec.label,
        "category": spec.category,
        "description": spec.description,
        "mp_id": spec.mp_id,
        "formula": st.formula_unit_cell,
        "spacegroup": f"{lat.spacegroup_symbol} ({lat.spacegroup_number})",
        "crystal_system": lat.crystal_system,
        "lattice": {
            k: getattr(lat, k) for k in ("a", "b", "c", "alpha", "beta", "gamma")
        },
        "sites": [
            {"el": s["species"][0]["element"], "frac": s["abc"]} for s in sites
        ],
        "electrons": h.num_electrons,
        "spin_polarized": h.spin_polarized,
        "functional": entry.reference.provenance.functional,
        "ecut_ev": h.basis.cutoff_energy_ev,
        "num_plane_waves": h.basis.num_plane_waves,
        "hash": entry.canonical_hash(),
        "retrieved_at": entry.reference.provenance.retrieved_at,
        "entry": to_dict(entry),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "fixtures")
    ap.add_argument("--site", type=Path, help="also write landing-page data here")
    args = ap.parse_args(argv)

    failures = 0
    records: list[dict] = []
    for spec in TIER1:
        entry = fetch_entry_from_mp(spec.mp_id, tags=["benchmark", "tier1", spec.key])
        problems = check_entry(spec, entry)
        if problems:
            failures += 1
            print(f"[FAIL] {spec.key} ({spec.mp_id}): " + "; ".join(problems))
            continue
        path = write_entry_json(entry, args.out / spec.fixture_name)
        print(f"[ ok ] {spec.key} ({spec.mp_id}) -> {path}")
        if args.site:
            with _open_client(None, MPAdapterConfig()) as mpr:
                sites = _summary_doc(mpr, spec.mp_id, None)["structure"]["sites"]
            records.append(site_record(spec, entry, sites))
    if args.site and records and not failures:
        args.site.parent.mkdir(parents=True, exist_ok=True)
        args.site.write_text(json.dumps(records, indent=1) + "\n", encoding="utf-8")
        print(f"[ ok ] site data -> {args.site}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
