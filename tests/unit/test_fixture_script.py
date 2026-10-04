"""The fixture builder must be runnable the way the docs say."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "benchmarks/build_tier1_fixtures.py"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT, capture_output=True, text=True,
        timeout=60, env=env,
    )


def test_help_works_by_path_and_as_module() -> None:
    for args in ([str(SCRIPT), "--help"], ["-m", "benchmarks.build_tier1_fixtures", "--help"]):
        r = _run(*args)
        assert r.returncode == 0, r.stderr
        assert "--site" in r.stdout


def test_missing_api_key_is_a_clean_error(tmp_path: Path) -> None:
    import os

    env = {k: v for k, v in os.environ.items() if k != "MP_API_KEY"}
    env["QMATBRIDGE_ENV_FILE"] = str(tmp_path / "no-such.env")  # ignore a real .env
    r = _run(str(SCRIPT), "--out", str(tmp_path), env=env)
    assert r.returncode == 2
    assert "MP_API_KEY" in r.stderr
    assert "Traceback" not in r.stderr


# ------------------------------------------------------------------ .env loading


def test_load_dotenv_reads_values_without_overriding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from benchmarks.build_tier1_fixtures import load_dotenv

    f = tmp_path / ".env"
    f.write_text(
        "# comment\n\nMP_API_KEY='from-file'\nexport OTHER_X=\"quoted\"\nEMPTY=\nbad line\n"
    )
    monkeypatch.delenv("MP_API_KEY", raising=False)
    monkeypatch.delenv("OTHER_X", raising=False)
    monkeypatch.delenv("EMPTY", raising=False)
    load_dotenv(f)
    assert os.environ["MP_API_KEY"] == "from-file"
    assert os.environ["OTHER_X"] == "quoted"
    assert "EMPTY" not in os.environ

    monkeypatch.setenv("MP_API_KEY", "already-set")
    load_dotenv(f)
    assert os.environ["MP_API_KEY"] == "already-set"  # real env wins


def test_load_dotenv_missing_file_is_a_noop(tmp_path: Path) -> None:
    from benchmarks.build_tier1_fixtures import load_dotenv

    load_dotenv(tmp_path / "nope.env")


def test_secret_files_are_gitignored_but_example_is_not() -> None:
    def ignored(name: str) -> bool:
        r = subprocess.run(
            ["git", "check-ignore", "-q", name], cwd=ROOT, capture_output=True
        )
        return r.returncode == 0

    for secret in (".env", ".env.local", "prod.env", "api_keys.json"):
        assert ignored(secret), f"{secret} must be gitignored"
    assert not ignored(".env.example")


def test_gitignore_and_example_hold_no_key_value() -> None:
    import re

    for name in (".gitignore", ".env.example"):
        text = (ROOT / name).read_text()
        assert not re.search(r"MP_API_KEY\s*=\s*\S", text), name
        assert not re.search(r"\b[A-Za-z0-9]{32}\b", text), name
