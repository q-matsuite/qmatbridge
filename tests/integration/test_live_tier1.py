"""Live Materials Project checks for the Tier-1 materials.

Marked ``integration``: excluded from the default run and from pull-request CI.
Run by the scheduled workflow (``.github/workflows/integration.yml``) or locally::

    pytest -m integration -o addopts="--tb=short"

with ``MP_API_KEY`` exported or in a gitignored ``.env``.  A failure here means
either the adapter broke or Materials Project changed what it serves; the
message says which fixture to regenerate.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from benchmarks.build_tier1_fixtures import RUN_TYPE, check_entry, load_dotenv
from benchmarks.tier1 import TIER1, BenchmarkSpec
from qmatbridge.adapters.materials_project import MPAdapterConfig, fetch_entry_from_mp
from qmatbridge.io import read_entry_json

ROOT = Path(__file__).resolve().parents[2]

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("MP_API_KEY"), reason="MP_API_KEY not set"),
]


def fetch(spec: BenchmarkSpec):  # type: ignore[no-untyped-def]
    return fetch_entry_from_mp(
        spec.mp_id,
        config=MPAdapterConfig(run_types=(RUN_TYPE[spec.functional],)),
        tags=["benchmark", "tier1", spec.key],
    )


@pytest.mark.parametrize("spec", TIER1, ids=lambda s: s.key)
def test_live_entry_satisfies_spec(spec: BenchmarkSpec) -> None:
    entry = fetch(spec)
    assert check_entry(spec, entry) == []


@pytest.mark.parametrize("spec", TIER1, ids=lambda s: s.key)
def test_live_entry_matches_committed_fixture(spec: BenchmarkSpec) -> None:
    """Drift check: the live record still gives the committed fixture's Hamiltonian."""
    committed = read_entry_json(ROOT / "benchmarks/fixtures" / spec.fixture_name)
    live = fetch(spec)
    hint = (
        f"Materials Project now serves different data for {spec.mp_id}; "
        "regenerate with `python -m benchmarks.build_tier1_fixtures --site "
        "website/data/examples.json` and review the diff."
    )
    assert live.canonical_hash() == committed.canonical_hash(), hint
    assert (
        live.hamiltonian.basis.num_plane_waves
        == committed.hamiltonian.basis.num_plane_waves
    ), hint
