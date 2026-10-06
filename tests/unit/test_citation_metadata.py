"""Citation metadata must agree across files (and with the package version)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tools.release_info import package_version

ROOT = Path(__file__).resolve().parents[2]


def cff_field(text: str, key: str) -> str:
    m = re.search(rf'^{key}:\s*"?([^"\n]+)"?\s*$', text, flags=re.M)
    assert m, f"CITATION.cff has no {key}"
    return m.group(1).strip()


def test_citation_cff_version_matches_the_package() -> None:
    """Releasing means bumping pyproject.toml *and* CITATION.cff; forgetting one fails here."""
    cff = (ROOT / "CITATION.cff").read_text()
    assert cff_field(cff, "version") == package_version()


def test_author_is_consistent_everywhere() -> None:
    cff = (ROOT / "CITATION.cff").read_text()
    assert 'family-names: "dos Reis"' in cff
    assert "given-names: Roberto" in cff
    assert "affiliation: q-matsuite" in cff

    for rel in ("README.md", "website/index.template.html"):
        text = (ROOT / rel).read_text()
        assert "author       = {{dos Reis}, Roberto}," in text, rel
        assert "organization = {q-matsuite}," in text, rel
        assert re.search(r"version\s*=\s*\{%s\}" % re.escape(package_version()), text), rel

    zen = json.loads((ROOT / ".zenodo.json").read_text())
    assert zen["creators"] == [{"name": "dos Reis, Roberto", "affiliation": "q-matsuite"}]


def test_no_stale_author_spelling_in_credits() -> None:
    """'Roberto Reis' was a mis-spelling of the author's name (LICENSE is deliberately excluded)."""
    skip = {"LICENSE", "CHANGELOG.md"}
    offenders = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if (
            not path.is_file()
            or path.suffix not in {".md", ".html", ".toml", ".cff", ".json", ".py", ".yml"}
            or any(p in {".git", ".venv", "proposal", "node_modules", "site", "_site"} for p in rel.parts)
            or rel.name in skip
            or "planning" in rel.parts
            or rel.parts[:2] == ("tests", "unit")
        ):
            continue
        if "Roberto Reis" in path.read_text(errors="ignore"):
            offenders.append(str(rel))
    assert not offenders, offenders


def test_zenodo_metadata_is_well_formed() -> None:
    zen = json.loads((ROOT / ".zenodo.json").read_text())
    assert zen["upload_type"] == "software" and zen["access_right"] == "open"
    assert zen["title"] == cff_field((ROOT / "CITATION.cff").read_text(), "title")
    assert zen["license"] == "MIT"
    assert all(r["identifier"].startswith("https://") for r in zen["related_identifiers"])
