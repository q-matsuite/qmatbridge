"""Tests for tools/build_site.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.build_site import MARKER, build


def test_embeds_data_and_escapes_script_end(tmp_path: Path) -> None:
    tpl = tmp_path / "t.html"
    tpl.write_text(f"<script>{MARKER}</script>")
    data = tmp_path / "d.json"
    data.write_text(json.dumps([{"label": "x</script>y"}]))
    out = tmp_path / "o.html"
    assert build(data, tpl, out) == 1
    html = out.read_text()
    assert "</script>y" not in html and "<\\/script>y" in html


def test_missing_data_gives_empty_list(tmp_path: Path) -> None:
    tpl = tmp_path / "t.html"
    tpl.write_text(f"<script>{MARKER}</script>")
    out = tmp_path / "o.html"
    assert build(tmp_path / "none.json", tpl, out) == 0
    assert out.read_text() == "<script>[]</script>"


def test_template_without_marker_fails(tmp_path: Path) -> None:
    tpl = tmp_path / "t.html"
    tpl.write_text("<p>no marker</p>")
    with pytest.raises(SystemExit):
        build(tmp_path / "none.json", tpl, tmp_path / "o.html")


def test_real_template_has_marker() -> None:
    root = Path(__file__).resolve().parents[2]
    assert MARKER in (root / "website/index.template.html").read_text()
