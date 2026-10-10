"""Tests for the OPTIMADE adapter, using recorded-shape responses (no network)."""

from __future__ import annotations

import json
import urllib.error
from typing import Any

import pytest

from qmatbridge.adapters.optimade import (
    OptimadeAdapter,
    OptimadeAdapterConfig,
    fetch_entry_from_optimade,
    fetch_hamiltonian_metadata_from_optimade,
    fetch_structure_metadata_from_optimade,
    hamiltonian_from_optimade,
    structure_from_optimade_doc,
)
from qmatbridge.registry import get_adapter

# Shape of https://optimade.materialsproject.org/v1/structures/mp-149 (a
# non-standard primitive cell whose positions lie outside the unit cell).
SI_DOC: dict[str, Any] = {
    "id": "mp-149",
    "type": "structures",
    "attributes": {
        "last_modified": "2023-03-11T20:40:53.667000",
        "dimension_types": [1, 1, 1],
        "lattice_vectors": [
            [3.333573, 0.0, 1.924639],
            [1.111191, 3.142924, 1.924639],
            [0.0, 0.0, 3.849278],
        ],
        "cartesian_site_positions": [
            [3.8891685, 2.7500585, 6.7362365],
            [0.5555955, 0.3928655, 0.9623195],
        ],
        "species": [
            {"name": "Si", "chemical_symbols": ["Si"], "concentration": [1.0]}
        ],
        "species_at_sites": ["Si", "Si"],
    },
}


def replay(doc: dict[str, Any] | None = SI_DOC, seen: list[str] | None = None, **kw):
    def get(url: str, timeout: float) -> bytes:
        if seen is not None:
            seen.append(url)
        if doc is None:
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)  # type: ignore[arg-type]
        return json.dumps({"data": doc}).encode()

    return OptimadeAdapterConfig(http_get=get, backoff_s=0.0, encut_ev=520.0, **kw)


def with_attrs(**changes: Any) -> dict[str, Any]:
    return {**SI_DOC, "attributes": {**SI_DOC["attributes"], **changes}}


def test_structure_from_doc() -> None:
    s = structure_from_optimade_doc(SI_DOC)
    assert s.formula_reduced == "Si" and s.formula_unit_cell == "Si2"
    assert s.num_sites == 2 and s.species == ["Si", "Si"]
    assert s.lattice.a == pytest.approx(3.8493, abs=1e-3)
    assert s.lattice.volume_ang3 == pytest.approx(40.0, abs=0.5)
    # Positions are wrapped into [0, 1): both atoms sit on the diamond sites.
    for site in s.sites:
        assert all(0.0 <= x < 1.0 for x in site.frac_coords)
    f0, f1 = (s_.frac_coords for s_ in s.sites)
    shift = [(b - a) % 1.0 for a, b in zip(f0, f1)]
    assert shift == pytest.approx([0.25, 0.25, 0.25], abs=1e-4) or [
        (1 - x) % 1.0 for x in shift
    ] == pytest.approx([0.25, 0.25, 0.25], abs=1e-4)


def test_fractional_roundtrip() -> None:
    doc = with_attrs(
        lattice_vectors=[[4.0, 0, 0], [0, 5.0, 0], [0, 0, 6.0]],
        cartesian_site_positions=[[2.0, 1.25, 4.5], [-1.0, 0, 6.0]],
    )
    s = structure_from_optimade_doc(doc)
    assert s.sites[0].frac_coords == pytest.approx((0.5, 0.25, 0.75))
    assert s.sites[1].frac_coords == pytest.approx((0.75, 0.0, 0.0))


def test_fetch_entry_by_provider_prefix() -> None:
    seen: list[str] = []
    entry = fetch_entry_from_optimade("mp:mp-149", replay(seen=seen), tags=["si"])
    assert seen == ["https://optimade.materialsproject.org/v1/structures/mp-149"]
    prov = entry.reference.provenance
    assert prov.primary.source == "optimade:mp"
    assert prov.primary.identifier == "mp:mp-149"
    assert prov.functional is None  # not defined by OPTIMADE, not invented
    assert prov.retrieved_at is not None
    assert entry.hamiltonian.num_electrons == 8
    assert entry.hamiltonian.valence_charges == {"Si": 4.0}
    assert entry.hamiltonian.basis.cutoff_energy_ev == 520.0
    assert "cutoff_energy_ev" in entry.hamiltonian.metadata["assumed"]
    assert entry.tags == ["si"]
    assert len(entry.canonical_hash()) == 64


def test_custom_base_url_and_provenance() -> None:
    seen: list[str] = []
    cfg = replay(
        seen=seen,
        base_url="https://example.org/optimade/",
        functional="PBE",
        code="VASP",
    )
    entry = fetch_entry_from_optimade("abc-1", cfg)
    assert seen == ["https://example.org/optimade/v1/structures/abc-1"]
    assert entry.reference.provenance.primary.source == "optimade:example.org"
    assert entry.reference.provenance.functional == "PBE"
    assert entry.reference.provenance.code == "VASP"


def test_no_server_configured() -> None:
    with pytest.raises(ValueError, match="no OPTIMADE server"):
        fetch_structure_metadata_from_optimade("mp-149", replay())


def test_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unknown OPTIMADE provider"):
        fetch_structure_metadata_from_optimade("x", replay(provider="nope"))


@pytest.mark.parametrize("bad", ["", "mp:", "mp:a/b", "mp:a?x=1", "mp:a b"])
def test_bad_identifier(bad: str) -> None:
    with pytest.raises(ValueError, match="not an OPTIMADE entry id"):
        fetch_structure_metadata_from_optimade(bad, replay(provider="mp"))


def test_requires_cutoff() -> None:
    cfg = replay()
    cfg.encut_ev = None
    cfg.provider = "mp"
    assert fetch_structure_metadata_from_optimade("mp-149", cfg).num_sites == 2
    with pytest.raises(ValueError, match="encut_ev"):
        fetch_entry_from_optimade("mp-149", cfg)


def test_valence_override_and_missing_element() -> None:
    doc = with_attrs(
        cartesian_site_positions=[[0, 0, 0], [1.9, 1.9, 1.9]],
        species=[
            {"name": "Na", "chemical_symbols": ["Na"], "concentration": [1.0]},
            {"name": "Cl", "chemical_symbols": ["Cl"], "concentration": [1.0]},
        ],
        species_at_sites=["Na", "Cl"],
    )
    cfg = replay(doc, provider="mp")
    with pytest.raises(ValueError, match=r"Na.*valence_charges"):
        fetch_entry_from_optimade("mp-1", cfg)
    cfg.valence_charges = {"Na": 7.0}
    entry = fetch_entry_from_optimade("mp-1", cfg)
    assert entry.hamiltonian.num_electrons == 14


def test_max_sites() -> None:
    cfg = replay(provider="mp", max_sites=1)
    with pytest.raises(ValueError, match="max_sites"):
        fetch_structure_metadata_from_optimade("mp-149", cfg)


def test_unknown_entry() -> None:
    with pytest.raises(ValueError, match="no OPTIMADE structure"):
        fetch_structure_metadata_from_optimade("mp-0", replay(None, provider="mp"))


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"dimension_types": [1, 1, 0]}, "periodic"),
        (
            {
                "species": [
                    {
                        "name": "SiGe",
                        "chemical_symbols": ["Si", "Ge"],
                        "concentration": [0.5, 0.5],
                    }
                ],
                "species_at_sites": ["SiGe", "SiGe"],
            },
            "disordered",
        ),
        (
            {
                "species": [
                    {"name": "Si", "chemical_symbols": ["Si"], "concentration": [0.9]}
                ]
            },
            "disordered",
        ),
        ({"species_at_sites": ["Si"]}, "disagree"),
        ({"species_at_sites": ["Si", "Xx"]}, "unknown species"),
        ({"lattice_vectors": None}, "lattice_vectors"),
        ({"lattice_vectors": [[1, 0, 0], [2, 0, 0], [0, 0, 1]]}, "lattice"),
        ({"cartesian_site_positions": [[0, 0, None], [0, 0, 0]]}, "null"),
    ],
)
def test_unsupported_or_malformed(changes: dict[str, Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        structure_from_optimade_doc(with_attrs(**changes))


def test_missing_attributes() -> None:
    with pytest.raises(ValueError, match="attributes"):
        structure_from_optimade_doc({"id": "x"})


def test_retries_then_succeeds() -> None:
    calls = {"n": 0}

    def flaky(url: str, timeout: float) -> bytes:
        calls["n"] += 1
        if calls["n"] == 1:
            return b"<html>502 Server Error</html>"
        if calls["n"] == 2:
            raise urllib.error.HTTPError(url, 503, "busy", {}, None)  # type: ignore[arg-type]
        return json.dumps({"data": SI_DOC}).encode()

    cfg = OptimadeAdapterConfig(
        provider="mp", http_get=flaky, backoff_s=0.0, encut_ev=520.0
    )
    assert fetch_entry_from_optimade("mp-149", cfg).hamiltonian.num_electrons == 8
    assert calls["n"] == 3


def test_gives_up_after_retries() -> None:
    def down(url: str, timeout: float) -> bytes:
        raise urllib.error.URLError("unreachable")

    cfg = OptimadeAdapterConfig(provider="mp", http_get=down, backoff_s=0.0, retries=1)
    with pytest.raises(ConnectionError, match="2 attempt"):
        fetch_structure_metadata_from_optimade("mp-149", cfg)


def test_server_error_payload() -> None:
    cfg = OptimadeAdapterConfig(
        provider="mp",
        http_get=lambda u, t: json.dumps({"errors": [{"status": "400"}]}).encode(),
    )
    with pytest.raises(ValueError, match="errors"):
        fetch_structure_metadata_from_optimade("mp-149", cfg)


def test_hamiltonian_fetch_and_converter() -> None:
    cfg = replay(provider="mp")
    ham = fetch_hamiltonian_metadata_from_optimade("mp-149", cfg)
    assert ham.num_electrons == 8
    s = structure_from_optimade_doc(SI_DOC)
    assert hamiltonian_from_optimade(s, cfg).basis.num_plane_waves == (
        ham.basis.num_plane_waves
    )


def test_registry_adapter() -> None:
    adapter = get_adapter("optimade", config=replay())
    assert isinstance(adapter, OptimadeAdapter)
    entry = adapter.fetch_entry("mp:mp-149")
    assert entry.reference.provenance.primary.identifier == "mp:mp-149"
    with pytest.raises(TypeError, match="unexpected"):
        adapter.fetch_entry("mp:mp-149", bogus=1)
