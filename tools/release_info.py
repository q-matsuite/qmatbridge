"""Release helpers used by ``.github/workflows/release.yml``.

Usage::

    python tools/release_info.py version              # print the package version
    python tools/release_info.py check-tag v0.2.0     # fail unless tag == version
    python tools/release_info.py notes 0.2.0          # print that CHANGELOG section

Standard library only, and Python 3.10 compatible.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package_version(pyproject: Path = ROOT / "pyproject.toml") -> str:
    """The ``[project]`` version from *pyproject*."""
    in_project = False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("["):
            in_project = line.strip() == "[project]"
        elif in_project and (m := re.match(r'version\s*=\s*"([^"]+)"', line)):
            return m.group(1)
    raise ValueError(f"no [project] version found in {pyproject}")


def changelog_notes(text: str, version: str) -> str:
    """The body of the ``## [version]`` section of a Keep-a-Changelog file.

    Raises:
        ValueError: If the section is missing or empty.
    """
    lines = text.splitlines()
    heading = re.compile(rf"##\s*\[{re.escape(version)}\]")
    start = next((i for i, ln in enumerate(lines) if heading.match(ln)), None)
    if start is None:
        raise ValueError(f"CHANGELOG has no section for version {version}")
    body: list[str] = []
    for ln in lines[start + 1 :]:
        if ln.startswith("## ["):
            break
        if re.match(r"\[[^\]]+\]:\s*\S+", ln):  # trailing link-reference definitions
            continue
        body.append(ln)
    notes = "\n".join(body).strip().strip("-").strip()
    if not notes:
        raise ValueError(f"CHANGELOG section for {version} is empty")
    return notes


def main(argv: list[str]) -> int:
    cmd, *args = argv
    try:
        if cmd == "version":
            print(package_version())
        elif cmd == "check-tag":
            tag, version = args[0], package_version()
            if tag.removeprefix("v") != version:
                print(
                    f"::error::tag {tag!r} does not match the package version "
                    f"{version!r}; bump pyproject.toml (and the CHANGELOG) or retag.",
                    file=sys.stderr,
                )
                return 1
            print(f"tag {tag} matches package version {version}")
        elif cmd == "notes":
            text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
            print(changelog_notes(text, args[0].removeprefix("v")))
        else:
            raise IndexError
    except (IndexError, ValueError) as exc:
        print(exc if isinstance(exc, ValueError) else __doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
