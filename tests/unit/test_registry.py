"""Tests for the plugin registry (qmatbridge.registry)."""

from __future__ import annotations

import importlib
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from qmatbridge.adapters import materials_project as mp
from qmatbridge.adapters.materials_project import MaterialsProjectAdapter
from qmatbridge.registry import (
    ADAPTER_GROUP,
    EXPORTER_GROUP,
    Adapter,
    Exporter,
    PluginError,
    UnknownPluginError,
    get_adapter,
    get_exporter,
    list_adapters,
    list_exporters,
)
from qmatbridge.schema import ExportMetadata, QMatEntry

PLUGIN_MODULE = '''
from qmatbridge.schema import ExportMetadata


class FakeAdapter:
    name = "fake_source"

    def __init__(self, prefix="fake"):
        self.prefix = prefix

    def fetch_entry(self, identifier, **options):
        raise NotImplementedError(f"{self.prefix}:{identifier}")


class FakeExporter:
    name = "fake_target"

    def export(self, entry, **options):
        return ExportMetadata(
            framework="fake", format="json", status="complete",
            artifact_path=options.get("path"),
        )


class WrongName:
    name = "something_else"

    def fetch_entry(self, identifier, **options):
        raise NotImplementedError


class NoMethod:
    name = "no_method"


class NeedsArgs:
    name = "needs_args"

    def __init__(self, required):
        pass

    def fetch_entry(self, identifier, **options):
        raise NotImplementedError
'''


def make_dist(root: Path, dist: str, entry_points: str, module: str = PLUGIN_MODULE) -> None:
    """Create an importable module plus a real *.dist-info with entry_points.txt."""
    (root / f"{dist}_mod.py").write_text(textwrap.dedent(module))
    info = root / f"{dist}-1.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {dist}\nVersion: 1.0\n")
    (info / "entry_points.txt").write_text(textwrap.dedent(entry_points))


@pytest.fixture()
def plugin_dir(tmp_path: Path) -> Iterator[Path]:
    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    try:
        yield tmp_path
    finally:
        sys.path.remove(str(tmp_path))
        for name in [m for m in sys.modules if m.endswith("_mod")]:
            del sys.modules[name]
        importlib.invalidate_caches()


# ------------------------------------------------------------------- built-ins


def test_materials_project_is_listed_as_builtin() -> None:
    by_name = {p.name: p for p in list_adapters()}
    info = by_name["materials_project"]
    assert info.builtin and info.group == ADAPTER_GROUP
    assert info.target.endswith(":MaterialsProjectAdapter")


def test_get_builtin_adapter_satisfies_protocol() -> None:
    adapter = get_adapter("materials_project")
    assert isinstance(adapter, Adapter)
    assert isinstance(adapter, MaterialsProjectAdapter)
    assert adapter.name == "materials_project"


def test_builtin_exporters_and_adapters() -> None:
    assert {p.name for p in list_exporters() if p.builtin} == {"numpy_planewave"}
    assert {p.name for p in list_adapters() if p.builtin} == {"materials_project", "oqmd"}


def test_mp_adapter_passes_arguments_through(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_fetch(identifier: str, **kw: Any) -> str:
        calls.append({"id": identifier, **kw})
        return "ENTRY"

    monkeypatch.setattr(mp, "fetch_entry_from_mp", fake_fetch)
    cfg = mp.MPAdapterConfig(max_sites=4)
    out = get_adapter("materials_project", config=cfg, api_key="k").fetch_entry(
        "mp-149", tags=["si"]
    )
    assert out == "ENTRY"
    assert calls == [{"id": "mp-149", "api_key": "k", "config": cfg, "tags": ["si"]}]


def test_mp_adapter_rejects_unknown_options() -> None:
    with pytest.raises(TypeError, match="unexpected option.*bogus"):
        get_adapter("materials_project").fetch_entry("mp-149", bogus=1)


# ------------------------------------------------- third-party plugin discovery


def test_third_party_plugins_are_discovered_via_entry_points(plugin_dir: Path) -> None:
    make_dist(
        plugin_dir,
        "thirdparty",
        f"""
        [{ADAPTER_GROUP}]
        fake_source = thirdparty_mod:FakeAdapter

        [{EXPORTER_GROUP}]
        fake_target = thirdparty_mod:FakeExporter
        """,
    )
    assert "thirdparty_mod" not in sys.modules

    adapters = {p.name: p for p in list_adapters()}
    assert not adapters["fake_source"].builtin
    assert adapters["fake_source"].target == "thirdparty_mod:FakeAdapter"
    assert "materials_project" in adapters  # built-ins still present
    assert [p.name for p in list_exporters()] == ["fake_target", "numpy_planewave"]
    # Listing is lazy: the plugin module has not been imported.
    assert "thirdparty_mod" not in sys.modules

    adapter = get_adapter("fake_source", prefix="hello")
    assert isinstance(adapter, Adapter)
    with pytest.raises(NotImplementedError, match="hello:abc"):
        adapter.fetch_entry("abc")

    exporter = get_exporter("fake_target")
    assert isinstance(exporter, Exporter)
    result = exporter.export(None, path="out.json")  # type: ignore[arg-type]
    assert isinstance(result, ExportMetadata)
    assert result.artifact_path == "out.json"
    assert "thirdparty_mod" in sys.modules


# ------------------------------------------------------------------- failures


def test_unknown_adapter_lists_what_is_available() -> None:
    with pytest.raises(UnknownPluginError, match=r"'nope'.*materials_project") as ei:
        get_adapter("nope")
    assert isinstance(ei.value, LookupError) and isinstance(ei.value, PluginError)


def test_unknown_exporter_when_none_installed() -> None:
    with pytest.raises(UnknownPluginError, match="no exporter named 'x'"):
        get_exporter("x")


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ("thirdparty_mod:WrongName", "reports name 'something_else'"),
        ("thirdparty_mod:NoMethod", "does not satisfy the Adapter protocol"),
        ("thirdparty_mod:DoesNotExist", "could not load adapter"),
        ("no_such_module_anywhere:X", "could not load adapter"),
        ("thirdparty_mod:NeedsArgs", "could not load adapter"),
    ],
)
def test_broken_plugins_raise_plugin_error(
    plugin_dir: Path, target: str, message: str
) -> None:
    name = target.split(":")[1]
    registered = {"WrongName": "wrong", "NoMethod": "no_method", "NeedsArgs": "needs_args"}
    reg_name = registered.get(name, "broken")
    make_dist(plugin_dir, "thirdparty", f"[{ADAPTER_GROUP}]\n{reg_name} = {target}\n")
    with pytest.raises(PluginError, match=message):
        get_adapter(reg_name)


def test_conflicting_registrations_are_rejected(plugin_dir: Path) -> None:
    make_dist(plugin_dir, "one", f"[{ADAPTER_GROUP}]\ndup = one_mod:FakeAdapter\n")
    make_dist(plugin_dir, "two", f"[{ADAPTER_GROUP}]\ndup = two_mod:FakeAdapter\n")
    with pytest.raises(PluginError, match=r"'dup' is registered twice"):
        list_adapters()


def test_plugin_cannot_shadow_a_builtin(plugin_dir: Path) -> None:
    make_dist(
        plugin_dir, "evil", f"[{ADAPTER_GROUP}]\nmaterials_project = evil_mod:FakeAdapter\n"
    )
    with pytest.raises(PluginError, match=r"registered twice.*built-in"):
        get_adapter("materials_project")


def test_same_target_registered_twice_is_fine(plugin_dir: Path) -> None:
    target = "qmatbridge.adapters.materials_project:MaterialsProjectAdapter"
    make_dist(plugin_dir, "dupe", f"[{ADAPTER_GROUP}]\nmaterials_project = {target}\n")
    assert [p.name for p in list_adapters()].count("materials_project") == 1


def test_protocols_are_structural() -> None:
    class Mine:
        name = "mine"

        def fetch_entry(self, identifier: str, **options: Any) -> QMatEntry:
            raise NotImplementedError

    assert isinstance(Mine(), Adapter)
    assert not isinstance(Mine(), Exporter)
