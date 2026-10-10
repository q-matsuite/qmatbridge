"""Plugin contract and registry for adapters and exporters.

An **adapter** turns a record from an upstream source into a
:class:`~qmatbridge.schema.QMatEntry`; an **exporter** turns a ``QMatEntry``
into a downstream format and reports what it produced as
:class:`~qmatbridge.schema.ExportMetadata`.  Both are small classes that
satisfy the protocols below, so a third-party package can add one without any
change to this repository.

Registering a plugin
--------------------
Declare an entry point in your package's ``pyproject.toml``::

    [project.entry-points."qmatbridge.adapters"]
    my_source = "my_package.adapter:MyAdapter"

    [project.entry-points."qmatbridge.exporters"]
    my_target = "my_package.exporter:MyExporter"

The target must be a class (or any zero-argument-callable) that returns an
object satisfying :class:`Adapter` / :class:`Exporter`, whose ``name`` equals
the entry-point name.

Using plugins
-------------
>>> from qmatbridge.registry import list_adapters, get_adapter
>>> [p.name for p in list_adapters()]            # doctest: +SKIP
['materials_project']
>>> adapter = get_adapter("materials_project")   # doctest: +SKIP
>>> entry = adapter.fetch_entry("mp-149")        # doctest: +SKIP

Listing is lazy: no plugin module is imported until :func:`get_adapter` /
:func:`get_exporter` is called, so a plugin's optional dependencies are only
needed when it is actually used.  Built-in plugins are listed in this module;
everything else is discovered through the entry-point groups.
"""

from __future__ import annotations

import importlib
import importlib.metadata as importlib_metadata
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from qmatbridge.schema import ExportMetadata, QMatEntry

__all__ = [
    "ADAPTER_GROUP",
    "EXPORTER_GROUP",
    "Adapter",
    "Exporter",
    "PluginError",
    "PluginInfo",
    "UnknownPluginError",
    "get_adapter",
    "get_exporter",
    "list_adapters",
    "list_exporters",
]

ADAPTER_GROUP = "qmatbridge.adapters"
EXPORTER_GROUP = "qmatbridge.exporters"


@runtime_checkable
class Adapter(Protocol):
    """Fetches a record from an upstream source as a ``QMatEntry``."""

    #: Registry name, equal to the entry-point name, e.g. ``"materials_project"``.
    name: str

    def fetch_entry(self, identifier: str, **options: Any) -> QMatEntry:
        """Return the entry for *identifier* (a source-specific ID)."""
        ...


@runtime_checkable
class Exporter(Protocol):
    """Writes a ``QMatEntry`` to a downstream format."""

    #: Registry name, equal to the entry-point name, e.g. ``"openfermion"``.
    name: str

    def export(self, entry: QMatEntry, **options: Any) -> ExportMetadata:
        """Export *entry* and describe the result.

        Implementations should record the framework, format, version and
        artifact path in the returned ``ExportMetadata``; attaching it to
        ``entry.exports`` is left to the caller.
        """
        ...


class PluginError(Exception):
    """A plugin is misregistered, cannot be loaded, or breaks the contract."""


class UnknownPluginError(PluginError, LookupError):
    """No plugin is registered under the requested name."""


@dataclass(frozen=True)
class PluginInfo:
    """What the registry knows about a plugin without importing it."""

    name: str
    group: str
    target: str  # "package.module:Attribute"
    builtin: bool


#: Plugins shipped with QMatBridge, by group.  Everything else comes from
#: entry points.  Kept here (not in pyproject) so they work from a source tree
#: that has not been re-installed.
_BUILTIN: dict[str, dict[str, str]] = {
    ADAPTER_GROUP: {
        "materials_project": (
            "qmatbridge.adapters.materials_project:MaterialsProjectAdapter"
        ),
        "oqmd": "qmatbridge.adapters.oqmd:OQMDAdapter",
        "optimade": "qmatbridge.adapters.optimade:OptimadeAdapter",
    },
    EXPORTER_GROUP: {
        "numpy_planewave": (
            "qmatbridge.exporters.numpy_planewave:NumpyPlaneWaveExporter"
        ),
    },
}


def _discover(group: str) -> dict[str, PluginInfo]:
    found = {
        name: PluginInfo(name, group, target, builtin=True)
        for name, target in _BUILTIN[group].items()
    }
    for ep in importlib_metadata.entry_points(group=group):
        existing = found.get(ep.name)
        if existing is not None and existing.target != ep.value:
            kind = "built-in " if existing.builtin else ""
            raise PluginError(
                f"{group}: name {ep.name!r} is registered twice with different targets "
                f"({kind}{existing.target!r} and {ep.value!r}); "
                "plugin names must be unique."
            )
        if existing is None:
            found[ep.name] = PluginInfo(ep.name, group, ep.value, builtin=False)
    return found


def _list(group: str) -> list[PluginInfo]:
    return sorted(_discover(group).values(), key=lambda p: p.name)


def _resolve(target: str) -> Any:
    module_name, _, attr = target.partition(":")
    obj: Any = importlib.import_module(module_name)
    for part in filter(None, attr.split(".")):
        obj = getattr(obj, part)
    return obj


def _get(
    group: str, kind: str, protocol: type, name: str, kwargs: dict[str, Any]
) -> Any:
    plugins = _discover(group)
    info = plugins.get(name)
    if info is None:
        available = ", ".join(sorted(plugins)) or "none installed"
        raise UnknownPluginError(f"no {kind} named {name!r} (available: {available})")
    try:
        factory = _resolve(info.target)
        plugin = factory(**kwargs) if callable(factory) else factory
    except PluginError:
        raise
    except Exception as exc:  # import errors, bad constructor arguments, ...
        raise PluginError(
            f"could not load {kind} {name!r} from {info.target!r}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(plugin, protocol):
        raise PluginError(
            f"{kind} {name!r} ({info.target!r}) does not satisfy the "
            f"{protocol.__name__} protocol (needs a `name` attribute and the "
            "required method)"
        )
    reported = getattr(plugin, "name", None)
    if reported != name:
        raise PluginError(
            f"{kind} registered as {name!r} reports name {reported!r}; "
            "the entry-point name and the class's `name` must match"
        )
    return plugin


def list_adapters() -> list[PluginInfo]:
    """Registered adapters, sorted by name.  Does not import any plugin."""
    return _list(ADAPTER_GROUP)


def list_exporters() -> list[PluginInfo]:
    """Registered exporters, sorted by name.  Does not import any plugin."""
    return _list(EXPORTER_GROUP)


def get_adapter(name: str, **kwargs: Any) -> Adapter:
    """Load and instantiate the adapter registered as *name*.

    Keyword arguments are passed to the adapter's constructor.

    Raises:
        UnknownPluginError: No adapter has that name.
        PluginError: The plugin fails to load or breaks the contract.
    """
    adapter: Adapter = _get(ADAPTER_GROUP, "adapter", Adapter, name, kwargs)
    return adapter


def get_exporter(name: str, **kwargs: Any) -> Exporter:
    """Load and instantiate the exporter registered as *name*.

    Raises:
        UnknownPluginError: No exporter has that name.
        PluginError: The plugin fails to load or breaks the contract.
    """
    exporter: Exporter = _get(EXPORTER_GROUP, "exporter", Exporter, name, kwargs)
    return exporter
