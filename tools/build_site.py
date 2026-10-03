"""Build website/index.html from website/index.template.html + example data.

Usage::

    python tools/build_site.py [--data website/data/examples.json]

The data file is produced by ``benchmarks/build_tier1_fixtures.py --site``.
It is embedded inline so the page is a single self-contained file.  If the
data file is missing, the page is built with no examples and the explorer
shows how to generate them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "__EXAMPLES_JSON__"


def build(data_path: Path, template: Path, out: Path) -> int:
    records = json.loads(data_path.read_text()) if data_path.exists() else []
    # "</" inside inline JSON would end the <script> element early.
    payload = json.dumps(records, separators=(",", ":")).replace("</", "<\\/")
    html = template.read_text(encoding="utf-8")
    if MARKER not in html:
        raise SystemExit(f"marker {MARKER} not found in {template}")
    out.write_text(html.replace(MARKER, payload), encoding="utf-8")
    return len(records)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "website/data/examples.json")
    ap.add_argument(
        "--template", type=Path, default=ROOT / "website/index.template.html"
    )
    ap.add_argument("--out", type=Path, default=ROOT / "website/index.html")
    a = ap.parse_args()
    n = build(a.data, a.template, a.out)
    print(f"wrote {a.out} with {n} example(s)")


if __name__ == "__main__":
    main()
