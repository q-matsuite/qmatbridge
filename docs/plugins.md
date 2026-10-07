# Writing a plugin

QMatBridge connects sources to targets through two small contracts. A third-party package
can add either one without changing this repository.

| Plugin | Does | Entry-point group |
| --- | --- | --- |
| **Adapter** | turns a record from an upstream source into a `QMatEntry` | `qmatbridge.adapters` |
| **Exporter** | turns a `QMatEntry` into a downstream format and reports what it produced | `qmatbridge.exporters` |

## The contracts

```python
from typing import Any
from qmatbridge.schema import ExportMetadata, QMatEntry


class MyAdapter:
    name = "my_source"                      # must equal the entry-point name

    def fetch_entry(self, identifier: str, **options: Any) -> QMatEntry: ...


class MyExporter:
    name = "my_target"                      # must equal the entry-point name

    def export(self, entry: QMatEntry, **options: Any) -> ExportMetadata: ...
```

The contracts are structural (`typing.Protocol`), so you don't need to import or subclass
anything from QMatBridge.

**Adapters** should record provenance faithfully: the source and identifier, the functional,
the pseudopotential family, the code, and the retrieval time. Two entries with the same
physics must end up with the same `canonical_hash()`.

**Exporters** should describe the result in the returned `ExportMetadata`: framework, format,
version, status and artifact path. They don't modify the entry; to record the export, the
caller appends the result to `entry.exports`.

## Registering

Declare an entry point in your package's `pyproject.toml`:

```toml
[project.entry-points."qmatbridge.adapters"]
my_source = "my_package.adapter:MyAdapter"

[project.entry-points."qmatbridge.exporters"]
my_target = "my_package.exporter:MyExporter"
```

The target must be a class (or any zero-argument callable) returning an object that satisfies
the contract. Constructor arguments with defaults are fine; callers can pass keyword arguments
to `get_adapter` / `get_exporter`.

After `pip install`, the plugin appears in the registry:

```python
from qmatbridge.registry import get_adapter, get_exporter, list_adapters

[p.name for p in list_adapters()]     # ['materials_project', 'my_source']

entry = get_adapter("my_source").fetch_entry("abc-123")
meta = get_exporter("my_target").export(entry, path="out.json")
entry.exports.append(meta)
```

## Behaviour to rely on

- **Listing is lazy.** `list_adapters()` / `list_exporters()` never import a plugin, so a
  plugin's optional dependencies are only needed when it is used.
- **Names are unique.** Two packages registering the same name for different targets, or a
  package trying to replace a built-in, raise `PluginError` rather than picking one silently.
- **Mistakes are explicit.** A plugin that cannot be imported or constructed, lacks the
  required members, or reports a `name` different from its registered name raises
  `PluginError` with the plugin name and target. An unknown name raises `UnknownPluginError`
  (also a `LookupError`) listing what is available.
- **Built-ins** are defined in `qmatbridge.registry` and work from a source checkout without
  re-installing; currently the adapters `materials_project` and `oqmd`, and the exporter `numpy_planewave`.

## Testing a plugin

Write golden-file tests: fetch or build a small fixture, export it, and compare the output
exactly. Keep network calls out of unit tests and mark live tests `@pytest.mark.integration`.
`qmatbridge.io.read_entry_json` loads committed fixtures back as entries.
