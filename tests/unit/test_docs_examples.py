"""The Python examples in the documentation must run as written.

Found while stress-testing 0.2.0: a snippet in the getting-started guide raised
NameError because it used a variable the page never defined.  Blocks run in order,
sharing one namespace per page, in a scratch directory.  Blocks that need an API
key or the network are skipped.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGES = ["README.md", "docs/getting-started.md"]
NEEDS_NETWORK = ("fetch_entry_from_mp", "MP_API_KEY", "MPRester")


def blocks(page: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", (ROOT / page).read_text(), flags=re.S)


@pytest.mark.parametrize("page", PAGES)
def test_documentation_examples_run_as_written(
    page: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, Any] = {"__name__": f"docs:{page}"}
    ran = 0
    for index, source in enumerate(blocks(page), start=1):
        if any(marker in source for marker in NEEDS_NETWORK):
            continue
        try:
            exec(compile(source, f"{page}#{index}", "exec"), namespace)  # noqa: S102
        except Exception as exc:  # pragma: no cover - failure path
            raise AssertionError(
                f"{page} code block {index} failed: {type(exc).__name__}: {exc}\n---\n{source}"
            ) from exc
        ran += 1
    assert ran >= 1, f"no runnable examples found in {page}"
    assert os.getcwd() == str(tmp_path)


def test_every_documented_example_page_exists() -> None:
    for page in PAGES:
        assert blocks(page), f"{page} has no python examples"
