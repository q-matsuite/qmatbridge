"""Tests for the OQMD adapter, using recorded-shape responses (no network)."""

from __future__ import annotations

import json
import urllib.error
from typing import Any

import pytest

from qmatbridge.adapters.oqmd import (
    OQMDAdapter,
    OQMDAdapterConfig,
    _normalise_entry_id,
    build_material_reference_from_oqmd,
    fetch_entry_from_oqmd,
    fetch_hamiltonian_metadata_from_oqmd,
    fetch_structure_metadata_from_oqmd,
    hamiltonian_from_oqmd,
    structure_from_oqmd_doc,
)
from qmatbridge.registry import get_adapter

SI_DOC: dict[str, Any] = {
    "name": "Si",
    "entry_id": 1214579,
    "spacegroup": "Fd-3m",
    "unit_cell": [[0, 2.73, 2.73], [2.73, 0, 2.73], [2.73, 2.73, 0]],
    "sites": ["Si @ 0.875 0.875 0.875", "Si @ 0.125 0.125 0.125"],
    "calculation_label": "standard",
}


def replay(doc: dict[str, Any] | None = SI_DOC, seen: list[str] | None = None):
    def get(url: str, timeout: float) -> bytes:
        if seen is not None:
            seen.append(url)
        return json.dumps({"data": [] if doc is None else [doc]}).encode()

    return OQMDAdapterConfig(http_get=get, backoff_s=0.0)


@pytest.mark.parametrize("raw", [1234, "1234", "oqmd-1234", " 1234 "])
def test_entry_id_normalisation(raw: int | str) -> None:
    ident, url = _normalise_entry_id(raw)
    assert ident == "oqmd-1234"
    assert url.endswith("/1234")


def test_build_reference() -> None:
    ref = build_material_reference_from_oqmd(
        1234, formula="Si", species=["Si", "Si"], num_sites=2
    )
    assert ref.provenance.primary.source == "oqmd"
    assert ref.provenance.primary.identifier == "oqmd-1234"
    assert ref.structure.num_sites == 2


def test_structure_from_doc() -> None:
    s = structure_from_oqmd_doc(SI_DOC)
    assert s.formula_reduced == "Si" and s.formula_unit_cell == "Si2"
    assert s.num_sites == 2 and len(s.sites) == 2
    assert s.lattice.a == pytest.approx(3.8608, abs=1e-3)
    assert s.lattice.alpha == pytest.approx(60.0)
    assert s.lattice.volume_ang3 == pytest.approx(40.693, abs=1e-2)
    assert s.lattice.spacegroup_symbol == "Fd-3m"
    assert s.lattice.spacegroup_number is None
    assert s.sites[0].frac_coords == (0.875, 0.875, 0.875)


def test_fetch_entry_end_to_end() -> None:
    seen: list[str] = []
    entry = fetch_entry_from_oqmd("oqmd-1214579", replay(seen=seen), tags=["si"])
    assert "filter=entry_id=1214579" in seen[0] and len(seen) == 1
    assert entry.reference.provenance.primary.identifier == "oqmd-1214579"
    assert entry.reference.provenance.functional == "PBE"
    assert entry.reference.provenance.retrieved_at is not None
    assert entry.hamiltonian.num_electrons == 8
    assert entry.hamiltonian.valence_charges == {"Si": 4.0}
    assert entry.hamiltonian.basis.cutoff_energy_ev == 520.0
    assert entry.hamiltonian.basis.num_plane_waves > 0
    assert "valence_charges" in entry.hamiltonian.metadata["assumed"]
    assert entry.tags == ["si"]
    assert len(entry.canonical_hash()) == 64


def test_valence_override_and_missing_element() -> None:
    doc = {**SI_DOC, "sites": ["Na @ 0 0 0", "Cl @ 0.5 0.5 0.5"]}
    with pytest.raises(ValueError, match=r"Na.*valence_charges"):
        fetch_entry_from_oqmd(1, replay(doc))
    cfg = replay(doc)
    cfg.valence_charges = {"Na": 7.0}
    entry = fetch_entry_from_oqmd(1, cfg)
    assert entry.hamiltonian.num_electrons == 14
    assert entry.hamiltonian.valence_charges == {"Cl": 7.0, "Na": 7.0}


def test_structure_and_hamiltonian_fetchers() -> None:
    cfg = replay()
    assert fetch_structure_metadata_from_oqmd(1, cfg).num_sites == 2
    assert fetch_hamiltonian_metadata_from_oqmd(1, cfg).num_electrons == 8


def test_max_sites() -> None:
    cfg = replay()
    cfg.max_sites = 1
    with pytest.raises(ValueError, match="max_sites"):
        fetch_structure_metadata_from_oqmd(1, cfg)


def test_unknown_entry() -> None:
    with pytest.raises(ValueError, match="no entry"):
        fetch_entry_from_oqmd(999, replay(None))


@pytest.mark.parametrize("bad", ["abc", "oqmd-x", "1.5", ""])
def test_bad_identifier(bad: str) -> None:
    with pytest.raises(ValueError, match="not an OQMD entry id"):
        fetch_entry_from_oqmd(bad, replay())


def test_retries_then_succeeds() -> None:
    calls = {"n": 0}

    def flaky(url: str, timeout: float) -> bytes:
        calls["n"] += 1
        if calls["n"] == 1:
            return b"<html>502 Server Error</html>"
        if calls["n"] == 2:
            raise urllib.error.HTTPError(url, 502, "bad gateway", {}, None)  # type: ignore[arg-type]
        return json.dumps({"data": [SI_DOC]}).encode()

    cfg = OQMDAdapterConfig(http_get=flaky, backoff_s=0.0)
    assert fetch_entry_from_oqmd(1, cfg).hamiltonian.num_electrons == 8
    assert calls["n"] == 3


def test_gives_up_after_retries() -> None:
    def down(url: str, timeout: float) -> bytes:
        raise urllib.error.URLError("unreachable")

    cfg = OQMDAdapterConfig(http_get=down, backoff_s=0.0, retries=2)
    with pytest.raises(ConnectionError, match="3 attempt"):
        fetch_entry_from_oqmd(1, cfg)


def test_client_error_is_not_retried() -> None:
    calls = {"n": 0}

    def forbidden(url: str, timeout: float) -> bytes:
        calls["n"] += 1
        raise urllib.error.HTTPError(url, 404, "nope", {}, None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="HTTP 404"):
        fetch_entry_from_oqmd(1, OQMDAdapterConfig(http_get=forbidden, backoff_s=0.0))
    assert calls["n"] == 1


@pytest.mark.parametrize(
    "doc",
    [
        {},
        {**SI_DOC, "sites": []},
        {**SI_DOC, "sites": ["Si 0 0 0"]},
        {**SI_DOC, "sites": ["Si @ 0 0"]},
        {**SI_DOC, "sites": ["Si @ 0 0 nan"]},
        {**SI_DOC, "unit_cell": [[1, 0, 0], [2, 0, 0], [0, 0, 1]]},
        {**SI_DOC, "unit_cell": [[0, 0, 0], [1, 0, 0], [0, 1, 0]]},
        {**SI_DOC, "unit_cell": "x"},
    ],
)
def test_malformed_documents_raise_value_error(doc: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        structure_from_oqmd_doc(doc)


def test_registered_as_builtin_adapter() -> None:
    adapter = get_adapter("oqmd", config=replay())
    assert isinstance(adapter, OQMDAdapter)
    assert adapter.fetch_entry("oqmd-1").hamiltonian.num_electrons == 8
    with pytest.raises(TypeError, match="unexpected"):
        adapter.fetch_entry("oqmd-1", bogus=1)


def test_hamiltonian_from_structure_directly() -> None:
    ham = hamiltonian_from_oqmd(structure_from_oqmd_doc(SI_DOC))
    assert ham.spin_polarized is True
