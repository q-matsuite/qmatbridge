"""Tests for the Materials Project adapter (offline; mp-api is faked)."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest

from qmatbridge.adapters import materials_project as mp
from qmatbridge.adapters.materials_project import (
    MPAdapterConfig,
    fetch_entry_from_mp,
    fetch_hamiltonian_metadata_from_mp,
    fetch_structure_metadata_from_mp,
    functional_from_mp_task_doc,
    hamiltonian_from_mp_task_doc,
    structure_from_mp_doc,
)
from qmatbridge.io import to_dict


def _site(el: str) -> dict[str, Any]:
    return {"species": [{"element": el, "occu": 1}]}


def si_doc() -> dict[str, Any]:
    return {
        "structure": {
            "lattice": {
                "a": 3.867, "b": 3.867, "c": 3.867,
                "alpha": 60.0, "beta": 60.0, "gamma": 60.0,
            },
            "sites": [_site("Si"), _site("Si")],
        },
        "symmetry": {"number": 227, "symbol": "Fd-3m", "crystal_system": "Cubic"},
    }


def task_doc(encut: float = 520.0, nelect: float = 8.0, ispin: int = 1) -> dict:
    return {
        "task_id": "mp-1000",
        "input": {
            "incar": {"ENCUT": encut, "ISPIN": ispin},
            "parameters": {"NELECT": nelect},
        },
    }


# ---------------------------------------------------------------- converters


def test_structure_from_doc_silicon() -> None:
    s = structure_from_mp_doc(si_doc())
    assert s.formula_reduced == "Si"
    assert s.formula_unit_cell == "Si2"
    assert s.num_sites == 2
    assert s.species == ["Si", "Si"]
    assert s.lattice.spacegroup_number == 227
    assert s.lattice.crystal_system == "cubic"
    assert s.lattice.a == pytest.approx(3.867)


def test_structure_formula_reduction_and_order() -> None:
    doc = si_doc()
    doc["structure"]["sites"] = [_site(e) for e in ("Ti", "Ti", "O", "O", "O", "O")]
    s = structure_from_mp_doc(doc)
    assert s.formula_reduced == "O2Ti"  # alphabetical (no carbon)
    assert s.formula_unit_cell == "O4Ti2"


def test_structure_hill_order_with_carbon() -> None:
    doc = si_doc()
    doc["structure"]["sites"] = [_site(e) for e in ("O", "H", "C", "H", "H", "H")]
    assert structure_from_mp_doc(doc).formula_unit_cell == "CH4O"


def test_structure_rejects_disorder_and_missing_keys() -> None:
    doc = si_doc()
    doc["structure"]["sites"][0] = {
        "species": [{"element": "Si", "occu": 0.5}, {"element": "Ge", "occu": 0.5}]
    }
    with pytest.raises(ValueError, match="disordered"):
        structure_from_mp_doc(doc)
    with pytest.raises(ValueError, match="missing"):
        structure_from_mp_doc({})


def test_hamiltonian_from_task_doc() -> None:
    s = structure_from_mp_doc(si_doc())
    h = hamiltonian_from_mp_task_doc(task_doc(), s)
    assert h.num_electrons == 8
    assert h.spin_polarized is False
    assert h.basis.type == "plane_wave"
    assert h.basis.cutoff_energy_ev == 520.0
    assert h.basis.num_plane_waves is not None
    assert 1000 < h.basis.num_plane_waves < 1250
    assert h.metadata["source_task_id"] == "mp-1000"


def test_hamiltonian_spin_polarized_and_errors() -> None:
    s = structure_from_mp_doc(si_doc())
    assert hamiltonian_from_mp_task_doc(task_doc(ispin=2), s).spin_polarized is True
    with pytest.raises(ValueError, match="ENCUT"):
        hamiltonian_from_mp_task_doc({"input": {"parameters": {"NELECT": 8}}}, s)
    with pytest.raises(ValueError, match="NELECT"):
        hamiltonian_from_mp_task_doc({"input": {"incar": {"ENCUT": 500}}}, s)
    with pytest.raises(ValueError, match="non-integer"):
        hamiltonian_from_mp_task_doc(task_doc(nelect=7.5), s)


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        ({"run_type": "GGA"}, "PBE"),
        ({"run_type": "GGA+U"}, "PBE+U"),
        ({"run_type": "r2SCAN"}, "r2SCAN"),
        ({"input": {"hubbards": {"Co": 3.32}}}, "PBE+U"),
        ({"input": {"hubbards": {}}}, "PBE"),
        ({}, "PBE"),
    ],
)
def test_functional_detection(task: dict, expected: str) -> None:
    assert functional_from_mp_task_doc(task) == expected


# ------------------------------------------------------------ fake MPRester


class _FakeMPR:
    def __init__(self, calc_types: dict[str, str] | None = None) -> None:
        sm = SimpleNamespace(
            search=lambda **kw: [
                SimpleNamespace(
                    structure=si_doc()["structure"], symmetry=si_doc()["symmetry"]
                )
            ]
            if kw["material_ids"] == ["mp-149"]
            else []
        )
        ct = (
            {"mp-1": "GGA Structure Optimization", "mp-1000": "GGA Static"}
            if calc_types is None
            else calc_types
        )
        self.materials = SimpleNamespace(
            summary=sm,
            search=lambda **kw: [SimpleNamespace(calc_types=ct)],
            tasks=SimpleNamespace(
                search=lambda **kw: [
                    {**task_doc(), "task_id": kw["task_ids"][0]}
                ]
            ),
        )

    def __enter__(self) -> _FakeMPR:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


@pytest.fixture()
def fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mp, "_open_client", lambda key, cfg: _FakeMPR())


def test_fetch_structure(fake_client: None) -> None:
    assert fetch_structure_metadata_from_mp("mp-149").formula_unit_cell == "Si2"


def test_fetch_unknown_material(fake_client: None) -> None:
    with pytest.raises(LookupError):
        fetch_structure_metadata_from_mp("mp-does-not-exist")


def test_fetch_respects_max_sites(fake_client: None) -> None:
    with pytest.raises(ValueError, match="max_sites"):
        fetch_structure_metadata_from_mp(
            "mp-149", config=MPAdapterConfig(max_sites=1)
        )


def test_fetch_hamiltonian_prefers_static_task(fake_client: None) -> None:
    h = fetch_hamiltonian_metadata_from_mp("mp-149")
    assert h.metadata["source_task_id"] == "mp-1000"


def test_fetch_entry_is_hashable_and_serializable(fake_client: None) -> None:
    e = fetch_entry_from_mp("mp-149", tags=["silicon"])
    assert e.reference.provenance.primary.identifier == "mp-149"
    assert e.reference.provenance.retrieved_at is not None
    assert e.reference.provenance.metadata["task_id"] == "mp-1000"
    assert e.tags == ["silicon"]
    assert len(e.canonical_hash()) == 64
    assert to_dict(e)["hamiltonian"]["num_electrons"] == 8


# ------------------------------------------------------ run-type selection

MULTI = {
    "t-gga-u": "GGA+U Static",
    "t-opt": "GGA+U Structure Optimization",
    "t-hse": "HSE06 Static",
    "t-r2": "r2SCAN Static",
}


@pytest.mark.parametrize(
    ("calc", "expected"),
    [
        ("GGA Static", "gga"),
        ("GGA+U Structure Optimization", "gga+u"),
        ("HSE06 Static", "hse06"),
        ("r2SCAN Static", "r2scan"),
        ("GGA NSCF Uniform", "gga"),
    ],
)
def test_run_type_of(calc: str, expected: str) -> None:
    assert mp._run_type_of(calc) == expected


def test_default_prefers_pbe_workflow_over_hse_and_r2scan() -> None:
    task = mp._pick_static_task(_FakeMPR(MULTI), "mp-149")
    assert task["task_id"] == "t-gga-u"
    assert task["_candidates"] == ["t-gga-u"]


def test_explicit_run_type_selects_hse() -> None:
    task = mp._pick_static_task(_FakeMPR(MULTI), "mp-149", ("HSE06",))
    assert task["task_id"] == "t-hse"


def test_run_type_preference_order() -> None:
    task = mp._pick_static_task(_FakeMPR(MULTI), "mp-149", ("r2SCAN", "GGA+U"))
    assert task["task_id"] == "t-r2"


def test_no_acceptable_run_type_is_a_clear_error() -> None:
    only_hse = {"t-hse": "HSE06 Static", "t-opt": "GGA Structure Optimization"}
    with pytest.raises(LookupError, match=r"hse06.*run_types"):
        mp._pick_static_task(_FakeMPR(only_hse), "mp-149")


def test_ties_are_broken_deterministically() -> None:
    two = {"b-2": "GGA Static", "a-1": "GGA Static"}
    task = mp._pick_static_task(_FakeMPR(two), "mp-149")
    assert task["_candidates"] == ["a-1", "b-2"] and task["task_id"] == "b-2"


def test_fetch_entry_uses_config_run_types(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mp, "_open_client", lambda key, cfg: _FakeMPR(MULTI))
    e = fetch_entry_from_mp("mp-149", config=MPAdapterConfig(run_types=("HSE06",)))
    assert e.reference.provenance.metadata["task_id"] == "t-hse"
    assert e.reference.provenance.metadata["candidate_task_ids"] == ["t-hse"]


# ---------------------------------------------------- client plumbing errors


def test_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MP_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        mp._resolve_api_key(None, MPAdapterConfig())


def test_api_key_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MP_API_KEY", "env")
    assert mp._resolve_api_key(None, MPAdapterConfig()) == "env"
    assert mp._resolve_api_key(None, MPAdapterConfig(api_key="cfg")) == "cfg"
    assert mp._resolve_api_key("arg", MPAdapterConfig(api_key="cfg")) == "arg"


def test_missing_mp_api_gives_install_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *a: Any, **k: Any) -> Any:
        if name.startswith("mp_api"):
            raise ImportError(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match=r"mp-api and pymatgen.*qmatbridge\[mp\].*-e"):
        mp._open_client("k", MPAdapterConfig())


# -------------------------------------------------------------- integration


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("MP_API_KEY"), reason="MP_API_KEY not set")
def test_live_silicon() -> None:  # pragma: no cover - network
    e = fetch_entry_from_mp("mp-149")
    assert e.reference.structure.formula_reduced == "Si"
    assert e.hamiltonian.num_electrons == 8


def test_missing_key_message_says_get_your_own(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MP_API_KEY", raising=False)
    with pytest.raises(ValueError) as exc:
        mp._resolve_api_key(None, MPAdapterConfig())
    msg = str(exc.value)
    assert "ships no keys" in msg and "materialsproject.org/api" in msg
