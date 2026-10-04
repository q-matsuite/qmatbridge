"""The fixture builder must be runnable the way the docs say."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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
    r = _run(str(SCRIPT), "--out", str(tmp_path), env=env)
    assert r.returncode == 2
    assert "MP_API_KEY" in r.stderr
    assert "Traceback" not in r.stderr
