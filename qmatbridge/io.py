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

import contextlib
import dataclasses
import functools
import json
import math
import os
import types
import typing
import uuid
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
SUPPORTED_SCHEMA_VERSIONS: tuple[str, ...] = ("0.1", "0.2")

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
    The output file is UTF-8 encoded and ends with a trailing newline.  The write
    is atomic: the data is serialised first and written through a temporary file,
    so a failure never truncates or corrupts an existing file.

    Args:
        entry:  Any dataclass instance (typically a ``QMatEntry``).
        path:   Destination file path.  Accepts ``str`` or ``pathlib.Path``.
        indent: JSON indentation width in spaces.  Default: 2.

    Returns:
        The resolved absolute ``Path`` of the written file.

    Raises:
        TypeError: If ``entry`` is not a dataclass instance, or holds a value
            that is not JSON-serialisable.
        ValueError: If the entry contains NaN or Infinity (not valid JSON).

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

    # Serialise first: if this fails, the destination has not been touched.
    try:
        text = json.dumps(
            to_dict(entry), indent=indent, ensure_ascii=False, allow_nan=False
        )
        text += "\n"
    except ValueError as exc:  # NaN / Infinity
        raise ValueError(
            f"cannot write {type(entry).__name__} as JSON: {exc}. NaN and Infinity "
            "are not valid JSON; replace them (or use None)."
        ) from exc

    # Write a sibling temp file, then atomically replace the destination, so an
    # interrupted or failed write can never leave a truncated or half-written file
    # where a good one used to be.  A symlinked destination is written through.
    dest = Path(os.path.realpath(path))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("x", encoding="utf-8") as fh:  # default (umask) permissions
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    return dest


# ---------------------------------------------------------------------------
# Reading entries back
# ---------------------------------------------------------------------------

_NONE_TYPE = type(None)


@functools.lru_cache(maxsize=None)
def _schema_of(cls: Any) -> tuple[dict[str, Any], dict[str, dataclasses.Field[Any]]]:
    """Type hints and fields of a dataclass, computed once per class.

    ``typing.get_type_hints`` re-evaluates the annotations on every call, which
    made decoding large entries (many nested objects) dramatically slow.
    """
    return typing.get_type_hints(cls), {f.name: f for f in dataclasses.fields(cls)}


def _check_finite(value: Any, path: str) -> None:
    """Reject NaN/Infinity anywhere inside free-form data (iteratively)."""
    stack = [(value, path)]
    while stack:
        v, p = stack.pop()
        if isinstance(v, float) and not math.isfinite(v):
            raise EntryFormatError(
                f"{p}: NaN and Infinity are not valid JSON values, got {v!r}"
            )
        if isinstance(v, dict):
            stack.extend((x, f"{p}.{k}") for k, x in v.items())
        elif isinstance(v, (list, tuple)):
            stack.extend((x, f"{p}[{i}]") for i, x in enumerate(v))


def _bad(path: str, expected: str, value: Any) -> EntryFormatError:
    return EntryFormatError(f"{path}: expected {expected}, got {type(value).__name__}")


def _decode(tp: Any, value: Any, path: str) -> Any:
    """Decode *value* as type annotation *tp*; *path* is used in errors."""
    if tp is Any:
        _check_finite(value, path)
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
        try:
            number = float(value)  # JSON may write 520 for 520.0
        except OverflowError:
            raise EntryFormatError(f"{path}: number is too large") from None
        if not math.isfinite(number):
            raise EntryFormatError(f"{path}: expected a finite number, got {value!r}")
        return number
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

    hints, fields = _schema_of(typing.cast(Any, cls))

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
    try:
        return from_dict(QMatEntry, data)
    except RecursionError:
        raise EntryFormatError("data is nested too deeply") from None


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON (NaN and Infinity are not allowed)")


def read_entry_json(path: str | Path) -> QMatEntry:
    """Read a ``QMatEntry`` from a JSON file written by :func:`write_entry_json`.

    The returned entry satisfies
    ``read_entry_json(write_entry_json(e, p)) == e`` and has the same
    ``canonical_hash()``.

    Raises:
        FileNotFoundError: If *path* does not exist (other ``OSError`` subclasses
            propagate, e.g. when *path* is a directory).
        EntryFormatError: If the file is not UTF-8 text, is not standard JSON
            (NaN/Infinity, over-deep nesting and so on), or does not match the
            schema (the message names the file and the offending field).
    """
    src = Path(path)
    try:
        text = src.read_bytes().decode("utf-8-sig")  # tolerate a UTF-8 BOM
    except UnicodeDecodeError as exc:
        raise EntryFormatError(f"{src}: not valid UTF-8 text ({exc.reason})") from exc
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except RecursionError:
        raise EntryFormatError(f"{src}: JSON is nested too deeply") from None
    except ValueError as exc:  # bad syntax, NaN/Infinity, over-long integers
        raise EntryFormatError(f"{src}: not valid JSON ({exc})") from exc
    try:
        return entry_from_dict(data)
    except EntryFormatError as exc:
        raise EntryFormatError(f"{src}: {exc}") from exc
