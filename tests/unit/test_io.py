"""Unit tests for qmatbridge.io."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from qmatbridge.io import to_dict, write_entry_json

if TYPE_CHECKING:
    from qmatbridge.schema import QMatEntry


# ---------------------------------------------------------------------------
# Local dataclasses for isolated to_dict tests
# ---------------------------------------------------------------------------

@dataclass
class _Leaf:
    x: int
    label: str


@dataclass
class _Node:
    name: str
    child: _Leaf
    items: list[_Leaf] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    pair: tuple[int, int] | None = None


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------

class TestToDict:
    def test_primitive_int(self) -> None:
        assert to_dict(42) == 42

    def test_primitive_string(self) -> None:
        assert to_dict("hello") == "hello"

    def test_primitive_float(self) -> None:
        assert to_dict(3.14) == pytest.approx(3.14)

    def test_primitive_none(self) -> None:
        assert to_dict(None) is None

    def test_primitive_bool(self) -> None:
        assert to_dict(True) is True

    def test_simple_dataclass(self) -> None:
        d = to_dict(_Leaf(x=7, label="a"))
        assert d == {"x": 7, "label": "a"}

    def test_nested_dataclass(self) -> None:
        node = _Node(name="top", child=_Leaf(x=1, label="b"))
        d = to_dict(node)
        assert d["name"] == "top"
        assert d["child"] == {"x": 1, "label": "b"}

    def test_list_of_dataclasses(self) -> None:
        node = _Node(
            name="top",
            child=_Leaf(x=0, label="z"),
            items=[_Leaf(x=1, label="a"), _Leaf(x=2, label="b")],
        )
        d = to_dict(node)
        assert len(d["items"]) == 2
        assert d["items"][0] == {"x": 1, "label": "a"}
        assert d["items"][1] == {"x": 2, "label": "b"}

    def test_tuple_becomes_list(self) -> None:
        node = _Node(name="t", child=_Leaf(x=0, label="z"), pair=(3, 4))
        d = to_dict(node)
        assert d["pair"] == [3, 4]
        assert isinstance(d["pair"], list)

    def test_plain_list_passthrough(self) -> None:
        assert to_dict([1, 2, 3]) == [1, 2, 3]

    def test_dict_values_converted(self) -> None:
        d = to_dict({"key": _Leaf(x=5, label="v")})
        assert d == {"key": {"x": 5, "label": "v"}}

    def test_empty_list(self) -> None:
        assert to_dict([]) == []

    def test_result_is_json_serializable(self) -> None:
        node = _Node(name="n", child=_Leaf(x=0, label="z"), pair=(1, 2))
        blob = json.dumps(to_dict(node))
        assert isinstance(blob, str)

    def test_class_itself_not_converted(self) -> None:
        # to_dict should not try to convert a class object (only instances)
        result = to_dict(_Leaf)
        assert result is _Leaf


# ---------------------------------------------------------------------------
# write_entry_json
# ---------------------------------------------------------------------------

class TestWriteEntryJson:
    def test_creates_file(self, tmp_path: Path, minimal_entry: QMatEntry) -> None:
        out = tmp_path / "entry.json"
        write_entry_json(minimal_entry, out)
        assert out.exists()

    def test_returns_resolved_absolute_path(
        self, tmp_path: Path, minimal_entry: QMatEntry
    ) -> None:
        out = tmp_path / "entry.json"
        result = write_entry_json(minimal_entry, out)
        assert result.is_absolute()
        assert result == out.resolve()

    def test_creates_parent_directories(
        self, tmp_path: Path, minimal_entry: QMatEntry
    ) -> None:
        out = tmp_path / "nested" / "deep" / "entry.json"
        write_entry_json(minimal_entry, out)
        assert out.exists()

    def test_output_is_valid_json(
        self, tmp_path: Path, minimal_entry: QMatEntry
    ) -> None:
        out = tmp_path / "entry.json"
        write_entry_json(minimal_entry, out)
        data = json.loads(out.read_text())
        assert isinstance(data, dict)
        assert "reference" in data
        assert "hamiltonian" in data

    def test_indentation_applied(
        self, tmp_path: Path, minimal_entry: QMatEntry
    ) -> None:
        out = tmp_path / "entry.json"
        write_entry_json(minimal_entry, out)
        content = out.read_text()
        # Two-space indent means lines like "  \"reference\":"
        assert '  "reference"' in content

    def test_ends_with_newline(
        self, tmp_path: Path, minimal_entry: QMatEntry
    ) -> None:
        out = tmp_path / "entry.json"
        write_entry_json(minimal_entry, out)
        assert out.read_text().endswith("\n")

    def test_accepts_string_path(
        self, tmp_path: Path, minimal_entry: QMatEntry
    ) -> None:
        out = str(tmp_path / "entry.json")
        write_entry_json(minimal_entry, out)
        assert Path(out).exists()

    def test_formula_in_output(
        self, tmp_path: Path, minimal_entry: QMatEntry
    ) -> None:
        out = tmp_path / "entry.json"
        write_entry_json(minimal_entry, out)
        data = json.loads(out.read_text())
        assert data["reference"]["structure"]["formula_reduced"] == "Si"

    def test_raises_for_non_dataclass(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="dataclass"):
            write_entry_json({"not": "a dataclass"}, tmp_path / "bad.json")  # type: ignore[arg-type]

    def test_raises_for_class_itself(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="dataclass"):
            write_entry_json(_Leaf, tmp_path / "bad.json")  # type: ignore[arg-type]

    def test_custom_indent(
        self, tmp_path: Path, minimal_entry: QMatEntry
    ) -> None:
        out = tmp_path / "entry.json"
        write_entry_json(minimal_entry, out, indent=4)
        content = out.read_text()
        assert '    "reference"' in content

    def test_silicon_fixture_matches_regenerated_json(self, tmp_path: Path) -> None:
        from examples.minimal_entry import make_silicon_entry

        silicon_entry = make_silicon_entry()
        fixture_path = Path(__file__).resolve().parents[2] / "examples" / "silicon_entry.json"
        expected = json.loads(fixture_path.read_text())

        assert expected == silicon_entry.to_dict()

        out = tmp_path / "silicon_entry.json"
        write_entry_json(silicon_entry, out)
        assert json.loads(out.read_text()) == expected
