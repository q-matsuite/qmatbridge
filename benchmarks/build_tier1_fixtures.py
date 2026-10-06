"""Generate Tier-1 benchmark fixtures from the live Materials Project API.

Usage::

    cp .env.example .env     # then put your key in .env (gitignored)
    pip install -e ".[mp]"
    python -m benchmarks.build_tier1_fixtures [--out benchmarks/fixtures]
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
import os
import sys
from pathlib import Path

# Allow ``python benchmarks/build_tier1_fixtures.py``: running a script by path
# puts benchmarks/ (not the repo root) on sys.path, so ``benchmarks.*`` would
# not import.  ``python -m benchmarks.build_tier1_fixtures`` needs no help.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.tier1 import TIER1, BenchmarkSpec
from qmatbridge.adapters.materials_project import (
    MPAdapterConfig,
    fetch_entry_from_mp,
)
from qmatbridge.io import to_dict, write_entry_json
from qmatbridge.schema import QMatEntry


def load_dotenv(path: Path | None = None) -> None:
    """Load ``KEY=VALUE`` lines from a gitignored ``.env`` into ``os.environ``.

    Existing environment variables win.  The file is the repo-root ``.env``
    unless ``QMATBRIDGE_ENV_FILE`` points elsewhere.  Values are never printed.
    """
    default = Path(__file__).resolve().parents[1] / ".env"
    path = path or Path(os.environ.get("QMATBRIDGE_ENV_FILE", default))
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        if key and value:
            os.environ.setdefault(key, value)


#: Materials Project run type that corresponds to each spec functional.  The spec
#: names the calculation we want; the adapter is asked for exactly that one.
RUN_TYPE: dict[str, str] = {"PBE": "GGA", "PBE+U": "GGA+U"}


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
    if entry.reference.provenance.functional != spec.functional:
        problems.append(
            f"functional {entry.reference.provenance.functional} "
            f"!= expected {spec.functional}"
        )
    if entry.hamiltonian.spin_polarized != spec.spin_polarized:
        problems.append(
            f"spin_polarized {entry.hamiltonian.spin_polarized} "
            f"!= expected {spec.spin_polarized}"
        )
    return problems


def site_record(spec: BenchmarkSpec, entry: QMatEntry) -> dict:
    """Assemble the per-material record consumed by the landing page.

    Atomic positions come from the entry itself (``structure.sites``).
    """
    if not entry.reference.structure.sites:
        raise ValueError(f"{spec.key}: entry has no atomic positions (structure.sites)")
    lat = entry.reference.structure.lattice
    h = entry.hamiltonian
    return {
        "key": spec.key,
        "label": spec.label,
        "category": spec.category,
        "description": spec.description,
        "mp_id": spec.mp_id,
        "formula": spec.cell_formula,
        "spacegroup": f"{lat.spacegroup_symbol} ({lat.spacegroup_number})",
        "crystal_system": lat.crystal_system,
        "lattice": {
            k: getattr(lat, k) for k in ("a", "b", "c", "alpha", "beta", "gamma")
        },
        "sites": [
            {"el": s.element, "frac": list(s.frac_coords)}
            for s in entry.reference.structure.sites
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

    load_dotenv()
    if not os.environ.get("MP_API_KEY"):
        print(
            "error: MP_API_KEY is not set.  Put it in a .env file at the repo root "
            "(see .env.example) or export it:\n  export MP_API_KEY=...",
            file=sys.stderr,
        )
        return 2

    failures = 0
    records: list[dict] = []
    for spec in TIER1:
        entry = fetch_entry_from_mp(
            spec.mp_id,
            config=MPAdapterConfig(run_types=(RUN_TYPE[spec.functional],)),
            tags=["benchmark", "tier1", spec.key],
        )
        problems = check_entry(spec, entry)
        if problems:
            failures += 1
            print(f"[FAIL] {spec.key} ({spec.mp_id}): " + "; ".join(problems))
            continue
        path = write_entry_json(entry, args.out / spec.fixture_name)
        print(f"[ ok ] {spec.key} ({spec.mp_id}) -> {path}")
        if args.site:
            records.append(site_record(spec, entry))
    if args.site and records and not failures:
        args.site.parent.mkdir(parents=True, exist_ok=True)
        args.site.write_text(json.dumps(records, indent=1) + "\n", encoding="utf-8")
        print(f"[ ok ] site data -> {args.site}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
