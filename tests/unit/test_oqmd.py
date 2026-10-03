"""Tests for the OQMD adapter stub."""

from __future__ import annotations

import pytest

from qmatbridge.adapters.oqmd import (
    _normalise_entry_id,
    build_material_reference_from_oqmd,
    fetch_hamiltonian_metadata_from_oqmd,
    fetch_structure_metadata_from_oqmd,
)


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


def test_live_fetchers_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        fetch_structure_metadata_from_oqmd(1234)
    with pytest.raises(NotImplementedError):
        fetch_hamiltonian_metadata_from_oqmd(1234)
