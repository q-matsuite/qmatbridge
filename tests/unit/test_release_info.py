"""Tests for tools/release_info.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.release_info import ROOT, changelog_notes, main, package_version

CHANGELOG = """# Changelog

## [Unreleased]

### Added
- something pending

---

## [0.2.0] — 2026-11-01

### Added
- feature A
- feature B

### Fixed
- bug C

---

## [0.1.0] — 2026-06-03

Initial release.

[Unreleased]: https://example.com/compare/v0.1.0...HEAD
[0.1.0]: https://example.com/releases/tag/v0.1.0
"""


def test_notes_for_a_middle_section() -> None:
    notes = changelog_notes(CHANGELOG, "0.2.0")
    assert notes.startswith("### Added") and "feature B" in notes and "bug C" in notes
    assert "pending" not in notes and "Initial release" not in notes


def test_notes_for_the_last_section_drop_link_references() -> None:
    notes = changelog_notes(CHANGELOG, "0.1.0")
    assert notes == "Initial release."


def test_missing_and_empty_sections() -> None:
    with pytest.raises(ValueError, match="no section for version 9.9.9"):
        changelog_notes(CHANGELOG, "9.9.9")
    with pytest.raises(ValueError, match="empty"):
        changelog_notes("## [1.0.0] — x\n\n---\n\n## [0.9.0]\n- a\n", "1.0.0")


def test_package_version_reads_the_project_table(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text('[build-system]\nrequires = []\nversion = "wrong"\n\n[project]\nname = "x"\nversion = "1.2.3"\n')
    assert package_version(p) == "1.2.3"
    q = tmp_path / "none.toml"
    q.write_text('[project]\nname = "x"\n')
    with pytest.raises(ValueError):
        package_version(q)


def test_real_repo_version_is_well_formed() -> None:
    import re

    assert re.fullmatch(r"\d+\.\d+\.\d+([abrc.]+\d+)?", package_version(ROOT / "pyproject.toml"))


def test_check_tag(capsys: pytest.CaptureFixture[str]) -> None:
    v = package_version()
    assert main(["check-tag", f"v{v}"]) == 0
    assert main(["check-tag", "v999.0.0"]) == 1
    assert "does not match" in capsys.readouterr().err
    assert main(["notes", "999.0.0"]) == 2
    assert main(["bogus"]) == 2
