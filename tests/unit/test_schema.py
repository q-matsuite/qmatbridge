"""Unit tests for qmatbridge.schema."""

from __future__ import annotations

import json

import pytest

from qmatbridge.schema import (
    ExportMetadata,
    ExternalIdentifier,
    LatticeMetadata,
    OracleMetadata,
    QMatEntry,
    TermMetadata,
    _INDEX_ENCODINGS,
    _ORACLE_TYPES,
)


class TestExternalIdentifier:
    def test_required_fields(self) -> None:
        e = ExternalIdentifier(source="mp", identifier="mp-149")
        assert e.source == "mp"
        assert e.identifier == "mp-149"

    def test_optional_defaults(self) -> None:
        e = ExternalIdentifier(source="mp", identifier="mp-149")
        assert e.url is None
        assert e.metadata == {}

    def test_url_stored(self) -> None:
        e = ExternalIdentifier(
            source="mp",
            identifier="mp-149",
            url="https://materialsproject.org/materials/mp-149",
        )
        assert "materialsproject" in e.url  # type: ignore[operator]


class TestLatticeMetadata:
    def test_required_lengths_and_angles(self) -> None:
        lat = LatticeMetadata(
            a=5.0, b=5.0, c=5.0,
            alpha=90.0, beta=90.0, gamma=90.0,
        )
        assert lat.a == 5.0
        assert lat.gamma == 90.0

    def test_optional_crystallographic_fields(self) -> None:
        lat = LatticeMetadata(a=3.0, b=3.0, c=3.0, alpha=60.0, beta=60.0, gamma=60.0)
        assert lat.spacegroup_number is None
        assert lat.spacegroup_symbol is None
        assert lat.crystal_system is None
        assert lat.volume_ang3 is None


class TestTermMetadata:
    def test_new_fields_default_empty(self) -> None:
        t = TermMetadata(name="kinetic")
        assert t.coefficient_labels == []
        assert t.implementation_notes is None

    def test_coefficient_labels_stored(self) -> None:
        t = TermMetadata(name="kinetic", coefficient_labels=["T_0", "T_1"])
        assert t.coefficient_labels == ["T_0", "T_1"]

    def test_norms_stored(self) -> None:
        t = TermMetadata(name="kinetic", lambda_one_norm=124.3, lambda_spectral=91.7)
        assert t.lambda_one_norm == pytest.approx(124.3)
        assert t.lambda_spectral == pytest.approx(91.7)


class TestOracleMetadata:
    def test_new_fields_default_none(self) -> None:
        o = OracleMetadata(method="lcu")
        assert o.oracle_type is None
        assert o.index_encoding is None
        assert o.coefficient_sampling is None
        assert o.complexity == {}

    def test_new_fields_stored(self) -> None:
        o = OracleMetadata(
            method="lcu",
            oracle_type="SELECT_PREPARE",
            index_encoding="binary",
            coefficient_sampling="alias_sampling",
            complexity={"toffoli_count": 4_200_000},
        )
        assert o.oracle_type == "SELECT_PREPARE"
        assert o.complexity["toffoli_count"] == 4_200_000

    def test_controlled_vocabularies_present(self) -> None:
        assert "SELECT_PREPARE" in _ORACLE_TYPES
        assert "binary" in _INDEX_ENCODINGS


class TestExportMetadata:
    def test_status_defaults_to_pending(self) -> None:
        ex = ExportMetadata(framework="openfermion", format="InteractionOperator")
        assert ex.status == "pending"

    def test_target_name_defaults_none(self) -> None:
        ex = ExportMetadata(framework="qualtran", format="lcu_coefficients")
        assert ex.target_name is None

    def test_fields_stored(self) -> None:
        ex = ExportMetadata(
            framework="qualtran",
            format="lcu_coefficients",
            target_name="qualtran_Si",
            status="complete",
            version="0.4.0",
        )
        assert ex.status == "complete"
        assert ex.target_name == "qualtran_Si"


class TestQMatEntry:
    def test_defaults(self, minimal_entry: QMatEntry) -> None:
        assert minimal_entry.exports == []
        assert minimal_entry.schema_version == "0.1"

    def test_tags_stored(self, minimal_entry: QMatEntry) -> None:
        assert "silicon" in minimal_entry.tags

    def test_repr_contains_formula(self, minimal_entry: QMatEntry) -> None:
        assert "Si" in repr(minimal_entry)

    def test_repr_contains_source(self, minimal_entry: QMatEntry) -> None:
        assert "test_db" in repr(minimal_entry)

    def test_minimal_entry_uses_recognized_oracle_values(
        self, minimal_entry: QMatEntry
    ) -> None:
        oracle = minimal_entry.hamiltonian.oracle
        assert oracle is not None
        assert oracle.oracle_type in _ORACLE_TYPES
        assert oracle.index_encoding in _INDEX_ENCODINGS


class TestCanonicalHash:
    def test_deterministic(self, minimal_entry: QMatEntry) -> None:
        assert minimal_entry.canonical_hash() == minimal_entry.canonical_hash()

    def test_is_64_char_hex(self, minimal_entry: QMatEntry) -> None:
        h = minimal_entry.canonical_hash()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_changes_on_electron_count(self, minimal_entry: QMatEntry) -> None:
        h1 = minimal_entry.canonical_hash()
        minimal_entry.hamiltonian.num_electrons = 10
        assert minimal_entry.canonical_hash() != h1

    def test_changes_on_basis_cutoff(self, minimal_entry: QMatEntry) -> None:
        h1 = minimal_entry.canonical_hash()
        minimal_entry.hamiltonian.basis.cutoff_energy_ev = 400.0
        assert minimal_entry.canonical_hash() != h1

    def test_changes_on_formula(self, minimal_entry: QMatEntry) -> None:
        h1 = minimal_entry.canonical_hash()
        minimal_entry.reference.structure.formula_reduced = "GaAs"
        assert minimal_entry.canonical_hash() != h1

    def test_stable_across_metadata_mutation(self, minimal_entry: QMatEntry) -> None:
        h1 = minimal_entry.canonical_hash()
        minimal_entry.hamiltonian.metadata["irrelevant"] = True
        minimal_entry.reference.provenance.metadata["also_irrelevant"] = 42
        assert minimal_entry.canonical_hash() == h1

    def test_stable_across_tag_mutation(self, minimal_entry: QMatEntry) -> None:
        h1 = minimal_entry.canonical_hash()
        minimal_entry.tags.append("new_tag")
        assert minimal_entry.canonical_hash() == h1

    def test_stable_across_export_addition(self, minimal_entry: QMatEntry) -> None:
        h1 = minimal_entry.canonical_hash()
        minimal_entry.exports.append(
            ExportMetadata(framework="openfermion", format="InteractionOperator")
        )
        assert minimal_entry.canonical_hash() == h1


class TestToDict:
    def test_returns_dict(self, minimal_entry: QMatEntry) -> None:
        assert isinstance(minimal_entry.to_dict(), dict)

    def test_top_level_keys(self, minimal_entry: QMatEntry) -> None:
        d = minimal_entry.to_dict()
        assert set(d.keys()) == {
            "reference", "hamiltonian", "exports", "tags", "schema_version"
        }

    def test_nested_structure_preserved(self, minimal_entry: QMatEntry) -> None:
        d = minimal_entry.to_dict()
        assert "provenance" in d["reference"]
        assert "structure" in d["reference"]
        assert "basis" in d["hamiltonian"]

    def test_is_json_serializable(self, minimal_entry: QMatEntry) -> None:
        blob = json.dumps(minimal_entry.to_dict())
        assert isinstance(blob, str)

    def test_formula_survives_round_trip(self, minimal_entry: QMatEntry) -> None:
        d = minimal_entry.to_dict()
        assert d["reference"]["structure"]["formula_reduced"] == "Si"

    def test_schema_version_in_dict(self, minimal_entry: QMatEntry) -> None:
        assert minimal_entry.to_dict()["schema_version"] == "0.1"
