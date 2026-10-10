"""The functionality-tour notebook must run end to end, offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NB = ROOT / "examples/notebooks/qmatbridge_tour.ipynb"


def test_tour_notebook_runs_offline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("numpy")
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cells = json.loads(NB.read_text(encoding="utf-8"))["cells"]
    sources = ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]
    assert any("LIVE = False" in s for s in sources), "network switch must default off"

    monkeypatch.chdir(NB.parent)  # Jupyter starts the kernel in the notebook's folder
    ns: dict[str, object] = {}
    try:
        for i, src in enumerate(sources):
            exec(compile(src, f"<tour cell {i}>", "exec"), ns)  # noqa: S102
    finally:
        plt.close("all")

    # The exporter ran and the entry survived a JSON round trip with its record.
    assert ns["repo_root"] == ROOT
    assert ns["back"] == ns["e"]
    assert len(ns["back"].exports) == 1  # type: ignore[attr-defined]
