"""QMatBridge I/O helpers — standard-library-only serialization utilities.

Public API
----------
to_dict(obj)
    Recursively convert any dataclass, list, dict, tuple, or primitive into
    a plain Python dictionary tree suitable for JSON serialization.

write_entry_json(entry, path, indent=2)
    Serialize a QMatEntry (or any dataclass) to a JSON file.

from_dict(cls, data)
    Rebuild a dataclass (recursively) from the plain dict that ``to_dict``
    produces, checking every field's type.

entry_from_dict(data), read_entry_json(path)
    Rebuild a ``QMatEntry`` from a dict or a JSON file, rejecting
    unsupported ``schema_version`` values.  ``read_entry_json`` is the inverse
    of ``write_entry_json``.

Only the Python standard library is used.  No optional extras required.
"""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from pathlib import Path
from typing import Any, TypeVar

from qmatbridge.schema import QMatEntry

__all__ = [
    "SUPPORTED_SCHEMA_VERSIONS",
    "EntryFormatError",
    "entry_from_dict",
    "from_dict",
    "read_entry_json",
    "to_dict",
    "write_entry_json",
]

#: ``schema_version`` values this library can read.
SUPPORTED_SCHEMA_VERSIONS: tuple[str, ...] = ("0.1",)

T = TypeVar("T")


class EntryFormatError(ValueError):
    """Raised when data does not match the QMatBridge schema.

    The message starts with the dotted path of the offending field, e.g.
    ``hamiltonian.basis.cutoff_energy_ev: expected a number, got str``.
    """


def to_dict(obj: Any) -> Any:
    """Recursively convert a dataclass (or nested structure) to a plain dict.

    Conversion rules:

    - dataclass instance  → ``dict`` keyed by field name (recursive)
    - ``list``            → ``list`` (each element converted recursively)
    - ``tuple``           → ``list`` (JSON has no tuple type)
    - ``dict``            → ``dict`` (values converted recursively)
    - everything else     → returned as-is (str, int, float, bool, None)

    Args:
        obj: Any dataclass instance, collection, or primitive value.

    Returns:
        A plain, JSON-serializable Python object.

    Example::

        from qmatbridge.io import to_dict
        from qmatbridge.schema import LatticeMetadata

        lat = LatticeMetadata(a=3.867, b=3.867, c=3.867,
                              alpha=60.0, beta=60.0, gamma=60.0)
        d = to_dict(lat)
        assert d["a"] == 3.867
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: to_dict(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
        }
    if isinstance(obj, list):
        return [to_dict(v) for v in obj]
    if isinstance(obj, tuple):
        return [to_dict(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def write_entry_json(
    entry: Any,
    path: str | Path,
    indent: int = 2,
) -> Path:
    """Serialize a QMatEntry (or any dataclass) to a JSON file.

    Parent directories are created automatically if they do not exist.
    The output file is UTF-8 encoded and ends with a trailing newline.

    Args:
        entry:  Any dataclass instance (typically a ``QMatEntry``).
        path:   Destination file path.  Accepts ``str`` or ``pathlib.Path``.
        indent: JSON indentation width in spaces.  Default: 2.

    Returns:
        The resolved absolute ``Path`` of the written file.

    Raises:
        TypeError: If ``entry`` is not a dataclass instance.

    Example::

        from qmatbridge.io import write_entry_json
        path = write_entry_json(entry, "output/silicon.json")
        print(f"Wrote {path.stat().st_size} bytes to {path}")
    """
    if not dataclasses.is_dataclass(entry) or isinstance(entry, type):
        raise TypeError(
            "write_entry_json expects a dataclass instance, "
            f"got {type(entry).__name__!r}"
        )

    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    data = to_dict(entry)
    with dest.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent, ensure_ascii=False)
        fh.write("\n")

    return dest.resolve()


# ---------------------------------------------------------------------------
# Reading entries back
# ---------------------------------------------------------------------------

_NONE_TYPE = type(None)


def _bad(path: str, expected: str, value: Any) -> EntryFormatError:
    return EntryFormatError(f"{path}: expected {expected}, got {type(value).__name__}")


def _decode(tp: Any, value: Any, path: str) -> Any:
    """Decode *value* as type annotation *tp*; *path* is used in errors."""
    if tp is Any:
        return value

    origin = typing.get_origin(tp)
    args = typing.get_args(tp)

    # Optional[X] / X | Y
    if origin is typing.Union or origin is types.UnionType:
        if value is None and _NONE_TYPE in args:
            return None
        options = [a for a in args if a is not _NONE_TYPE]
        errors: list[str] = []
        for opt in options:
            try:
                return _decode(opt, value, path)
            except EntryFormatError as exc:
                errors.append(str(exc))
        raise EntryFormatError(errors[0] if len(errors) == 1 else f"{path}: no match")

    if dataclasses.is_dataclass(tp) and isinstance(tp, type):
        return from_dict(tp, value, _path=path)

    if tp is bool:
        if not isinstance(value, bool):
            raise _bad(path, "a boolean", value)
        return value
    if tp is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise _bad(path, "an integer", value)
        return value
    if tp is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _bad(path, "a number", value)
        return float(value)  # JSON may write 520 for 520.0
    if tp is str:
        if not isinstance(value, str):
            raise _bad(path, "a string", value)
        return value

    if origin is list:
        if not isinstance(value, list):
            raise _bad(path, "a list", value)
        return [_decode(args[0], v, f"{path}[{i}]") for i, v in enumerate(value)]

    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise _bad(path, "a list", value)
        if len(value) != len(args):
            raise EntryFormatError(
                f"{path}: expected {len(args)} items, got {len(value)}"
            )
        return tuple(
            _decode(a, v, f"{path}[{i}]") for i, (a, v) in enumerate(zip(args, value))
        )

    if origin is dict:
        if not isinstance(value, dict):
            raise _bad(path, "an object", value)
        return {k: _decode(args[1], v, f"{path}.{k}") for k, v in value.items()}

    raise TypeError(f"{path}: unsupported annotation {tp!r}")  # schema bug, not data


def from_dict(cls: type[T], data: Any, *, _path: str = "") -> T:
    """Rebuild a dataclass *cls* from a plain dict, the inverse of :func:`to_dict`.

    Nested dataclasses, lists, tuples and optional fields are rebuilt from the
    type annotations.  Reading is strict so that nothing is silently dropped or
    coerced: unknown keys, missing required fields and wrongly typed values
    raise :class:`EntryFormatError` naming the offending field.  The only
    coercion is integer to float, since JSON may write ``520`` for ``520.0``.

    Args:
        cls:  A dataclass type, e.g. ``LatticeMetadata`` or ``QMatEntry``.
        data: The dict to decode.

    Raises:
        EntryFormatError: If *data* does not match the schema.

    Example::

        from qmatbridge.io import from_dict, to_dict
        from qmatbridge.schema import LatticeMetadata

        lat = LatticeMetadata(a=3.8, b=3.8, c=3.8, alpha=60, beta=60, gamma=60)
        assert from_dict(LatticeMetadata, to_dict(lat)) == lat
    """
    here = _path or cls.__name__
    if not isinstance(data, dict):
        raise _bad(here, "an object", data)

    hints = typing.get_type_hints(cls)
    fields = {f.name: f for f in dataclasses.fields(cls)}  # type: ignore[arg-type]

    unknown = sorted(set(data) - set(fields))
    if unknown:
        raise EntryFormatError(f"{here}: unknown field(s) {', '.join(unknown)}")

    kwargs: dict[str, Any] = {}
    for name, f in fields.items():
        sub = f"{_path}.{name}" if _path else name
        if name in data:
            kwargs[name] = _decode(hints[name], data[name], sub)
        elif (
            f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING
        ):
            raise EntryFormatError(f"{sub}: required field is missing")
    return cls(**kwargs)


def entry_from_dict(data: Any) -> QMatEntry:
    """Rebuild a :class:`~qmatbridge.schema.QMatEntry` from a dict.

    Raises:
        EntryFormatError: If the data does not match the schema, or its
            ``schema_version`` is not in :data:`SUPPORTED_SCHEMA_VERSIONS`.
    """
    if isinstance(data, dict):
        version = data.get("schema_version", "0.1")
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise EntryFormatError(
                f"schema_version: {version!r} is not supported by this version of "
                f"QMatBridge (it reads: {', '.join(SUPPORTED_SCHEMA_VERSIONS)}). "
                "Upgrade QMatBridge or migrate the file."
            )
    return from_dict(QMatEntry, data)


def read_entry_json(path: str | Path) -> QMatEntry:
    """Read a ``QMatEntry`` from a JSON file written by :func:`write_entry_json`.

    The returned entry satisfies
    ``read_entry_json(write_entry_json(e, p)) == e`` and has the same
    ``canonical_hash()``.

    Raises:
        FileNotFoundError: If *path* does not exist.
        EntryFormatError: If the file is not valid JSON, or does not match the
            schema (the message names the file and the offending field).
    """
    src = Path(path)
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EntryFormatError(f"{src}: not valid JSON ({exc})") from exc
    try:
        return entry_from_dict(data)
    except EntryFormatError as exc:
        raise EntryFormatError(f"{src}: {exc}") from exc
