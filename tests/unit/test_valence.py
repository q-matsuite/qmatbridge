"""Schema 0.3: per-species valence charges."""

from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from qmatbridge.adapters.materials_project import (
    hamiltonian_from_mp_task_doc,
    valence_charges_from_mp_task_doc,
)
from qmatbridge.io import entry_from_dict, read_entry_json
from qmatbridge.schema import QMatEntry


@pytest.fixture
def si() -> QMatEntry:
    e = read_entry_json("benchmarks/fixtures/Si.json")
    e.hamiltonian.valence_charges = {"Si": 4.0}
    return e


def test_default_is_empty_and_total_is_none(si: QMatEntry) -> None:
    si.hamiltonian.valence_charges = {}
    assert si.valence_electron_total() is None
    si.check_electron_count()  # nothing to check


def test_total_matches_electrons(si: QMatEntry) -> None:
    assert si.valence_electron_total() == 8.0
    si.check_electron_count()


def test_mismatch_and_missing_element(si: QMatEntry) -> None:
    si.hamiltonian.valence_charges = {"Si": 5.0}
    with pytest.raises(ValueError, match="sum to 10"):
        si.check_electron_count()
    si.hamiltonian.valence_charges = {"Ge": 4.0}
    with pytest.raises(KeyError, match="Si"):
        si.valence_electron_total()


def test_round_trip_and_hash_unchanged(si: QMatEntry) -> None:
    before = copy.deepcopy(si)
    before.hamiltonian.valence_charges = {}
    assert si.canonical_hash() == before.canonical_hash()
    again = entry_from_dict(si.to_dict())
    assert again.hamiltonian.valence_charges == {"Si": 4.0}
    assert again == si


def test_reads_old_entries_without_the_field(si: QMatEntry) -> None:
    d = si.to_dict()
    del d["hamiltonian"]["valence_charges"]
    d["schema_version"] = "0.2"
    assert entry_from_dict(d).hamiltonian.valence_charges == {}


def test_bad_charge_types_rejected(si: QMatEntry) -> None:
    d = si.to_dict()
    d["hamiltonian"]["valence_charges"] = {"Si": "four"}
    with pytest.raises(ValueError, match="valence_charges"):
        entry_from_dict(d)


def task(zval=(4.0,), titel=("PAW_PBE Si 05Jan2001",), nelect=8.0):
    return {
        "input": {
            "incar": {"ENCUT": 520.0, "ISPIN": 1},
            "parameters": {"NELECT": nelect, "ZVAL": list(zval)},
            "potcar_spec": [{"titel": t} for t in titel],
        }
    }


def test_mp_charges_from_task_doc() -> None:
    assert valence_charges_from_mp_task_doc(task()) == {"Si": 4.0}
    two = task(zval=(3.0, 17.0), titel=("PAW_PBE Li_sv 23Jan2001", "PAW_PBE Co 06Sep2000"))
    assert valence_charges_from_mp_task_doc(two) == {"Li": 3.0, "Co": 17.0}


@pytest.mark.parametrize(
    "t",
    [
        {},
        {"input": {}},
        task(zval=()),
        task(zval=(4.0, 4.0)),
        task(titel=("garbage",)),
        task(zval=(float("nan"),)),
        task(zval=(-1.0,)),
        task(zval=(True,)),
        task(zval=(4.0, 5.0), titel=("PAW_PBE Si 1", "PAW_PBE Si_x 2")),
    ],
)
def test_mp_charges_never_guess(t: dict) -> None:
    assert valence_charges_from_mp_task_doc(t) == {}


def test_mp_hamiltonian_carries_charges(si: QMatEntry) -> None:
    ham = hamiltonian_from_mp_task_doc(task(), si.reference.structure)
    assert ham.valence_charges == {"Si": 4.0}
    assert replace(si, hamiltonian=ham).valence_electron_total() == 8.0
