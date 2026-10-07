"""The quickstart notebook must work wherever Jupyter starts its kernel."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NB = ROOT / "examples/notebooks/qmatbridge_quickstart.ipynb"


def _code_cells() -> list[str]:
    cells = json.loads(NB.read_text(encoding="utf-8"))["cells"]
    return ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]


def _run_setup_cell() -> dict[str, object]:
    # Cell 0 is the setup cell; drop plotting/data imports so the test stays light.
    src = "\n".join(
        line
        for line in _code_cells()[0].splitlines()
        if "matplotlib" not in line and "pandas" not in line
    )
    ns: dict[str, object] = {}
    exec(compile(src, "<notebook setup cell>", "exec"), ns)  # noqa: S102
    return ns


@pytest.mark.parametrize("sub", ["", "examples", "examples/notebooks"])
def test_repo_root_found_from_any_folder_in_the_checkout(
    monkeypatch: pytest.MonkeyPatch, sub: str
) -> None:
    monkeypatch.chdir(ROOT / sub)
    assert _run_setup_cell()["repo_root"] == ROOT


def test_clear_error_outside_a_checkout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="open this notebook from inside a checkout"):
        _run_setup_cell()


def test_scripts_are_not_run_via_cwd_relative_paths() -> None:
    # The cell that regenerates the example outputs by running the example scripts.
    runners = [c for c in _code_cells() if "subprocess.run" in c]
    assert runners, "no notebook cell runs the example scripts"
    for cell in runners:
        assert '"examples/' not in cell and "cwd=repo_root" in cell
