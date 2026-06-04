"""QMatBridge I/O helpers — standard-library-only serialization utilities.

Public API
----------
to_dict(obj)
    Recursively convert any dataclass, list, dict, tuple, or primitive into
    a plain Python dictionary tree suitable for JSON serialization.

write_entry_json(entry, path, indent=2)
    Serialize a QMatEntry (or any dataclass) to a JSON file.

Only the Python standard library is used.  No optional extras required.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

__all__ = ["to_dict", "write_entry_json"]


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
