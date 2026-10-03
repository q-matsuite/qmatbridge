# Contributing to QMatBridge

Thank you for your interest in contributing. QMatBridge is an early-stage open-source
project and we welcome contributions of all kinds: bug reports, database adapters,
Hamiltonian exporters, documentation improvements, and benchmark additions.

Before you begin, please read our [Code of Conduct](CODE_OF_CONDUCT.md) and review the
[project vision](docs/vision.md) to understand the architectural constraints.

---

## Table of Contents

- [Where to Start](#where-to-start)
- [Development Setup](#development-setup)
- [Contribution Workflow](#contribution-workflow)
- [Proposing Schema Changes](#proposing-schema-changes)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Adding a Database Adapter](#adding-a-database-adapter)
- [Adding a Hamiltonian Exporter](#adding-a-hamiltonian-exporter)
- [Commit Message Format](#commit-message-format)
- [Versioning Policy](#versioning-policy)

---

## Where to Start

| Contribution type | First step |
| --- | --- |
| Bug | Open a [bug report](https://github.com/QMatBridge/qmatbridge/issues/new?template=bug_report.yml) |
| New feature or adapter | Open a [feature request](https://github.com/QMatBridge/qmatbridge/issues/new?template=feature_request.yml) first |
| Schema change | Open an issue tagged `schema` and discuss before writing code |
| Documentation | PR welcome without a prior issue |
| Benchmark | Add to `benchmarks/` and update `benchmarks/README.md` |
| Question | Use [GitHub Discussions](https://github.com/QMatBridge/qmatbridge/discussions) |

If you are unsure whether your idea fits the project scope, open a Discussion first —
it is lower friction than an issue and maintainers check it regularly.

---

## Development Setup

```bash
git clone https://github.com/QMatBridge/qmatbridge.git
cd qmatbridge
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Install optional adapter extras as needed:

```bash
pip install -e ".[dev,mp,ase]"
```

Verify everything works:

```bash
pytest
ruff check .
mypy qmatbridge/
python examples/minimal_entry.py
```

---

## Contribution Workflow

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Write code** following the [Code Standards](#code-standards) below.

3. **Add or update tests.** All new public behaviour must be covered.

4. **Run the full check suite locally** before pushing:
   ```bash
   ruff check . && mypy qmatbridge/ && pytest --tb=short
   ```

5. **Open a pull request** against `main` using the PR template.
   Fill in every section — incomplete PRs will be sent back.

6. A maintainer will review within **7 business days**.
   Please respond to review comments within **14 days**;
   stale PRs will be closed but can be reopened at any time.

---

## Proposing Schema Changes

The three core dataclasses — `MaterialReference`, `HamiltonianMetadata`, `QMatEntry` —
form the stable contract of QMatBridge. Changes to them affect every adapter, exporter,
and downstream pipeline.

**Before writing any code for a schema change:**

1. Open a GitHub issue tagged `schema`.
2. Describe the physics motivation, the proposed field name and type, and whether it
   is backward-compatible (new optional field) or breaking (rename, type change, removal).
3. Allow at least one week for community discussion.
4. Obtain explicit approval from a maintainer before opening a PR.

Any change that alters the canonical hash algorithm requires a **minor version bump**
and a migration note in `CHANGELOG.md`. See the [Versioning Policy](#versioning-policy).

---

## Code Standards

| Requirement | Detail |
| --- | --- |
| Linter / formatter | `ruff` — config in `pyproject.toml`. Run `ruff check --fix .` |
| Type annotations | All public symbols must be annotated. `mypy --strict` must pass |
| Comments | Only for non-obvious physics invariants or workarounds. No docstring novels |
| Core dependencies | `qmatbridge/` core must remain **zero external dependencies** |
| Optional deps | Heavy libraries (numpy, pymatgen, openfermion) go in `pyproject.toml` optional extras |
| Python versions | Must be compatible with Python 3.10, 3.11, and 3.12 |

---

## Testing

```bash
pytest                            # all tests
pytest tests/test_schema.py       # one module
pytest --cov=qmatbridge           # with coverage report
pytest -m integration             # integration tests (require env vars, see below)
```

Guidelines:

- Unit tests live in `tests/unit/`; integration tests in `tests/integration/`
- Integration tests that call external APIs must be decorated
  `@pytest.mark.integration` and must be skipped when the relevant
  environment variable (e.g. `MP_API_KEY`) is not set
- Every new public function needs at minimum one happy-path and one
  error/edge-case test
- Benchmark scripts in `benchmarks/` are excluded from the default test run

---

## Adding a Database Adapter

Adapters live in `qmatbridge/adapters/<db_name>.py`.

```python
# qmatbridge/adapters/my_db.py
from __future__ import annotations

try:
    import my_db_client  # optional dependency
except ImportError as e:
    raise ImportError(
        "Install the 'mydb' extra: pip install qmatbridge[mydb]"
    ) from e

from qmatbridge.schema import HamiltonianMetadata, MaterialReference, QMatEntry


def fetch(material_id: str, **kwargs: object) -> QMatEntry:
    """Fetch a material from MyDB and return a QMatEntry."""
    ...
```

Checklist before opening a PR:

- [ ] Importable without the optional dependency installed (guard with `try/except`)
- [ ] `extra` dict captures all adapter-specific metadata
- [ ] `tests/integration/test_adapter_<name>.py` marked `@pytest.mark.integration`
- [ ] Adapter listed in `pyproject.toml` under a named optional extra

---

## Adding a Hamiltonian Exporter

Exporters live in `qmatbridge/exporters/<framework>.py`. They consume a `QMatEntry`
and return a downstream representation:

```python
# qmatbridge/exporters/openfermion.py
from qmatbridge.schema import QMatEntry


def to_openfermion(entry: QMatEntry):
    """Convert a QMatEntry to an OpenFermion InteractionOperator."""
    ...
```

---

## Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary in present tense>

[optional body — what and why, not how]

[optional footer: Closes #<issue>]
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`

Examples:
```
feat(adapters): add Materials Project adapter using mp-api
fix(schema): exclude extra dicts from canonical hash computation
docs(vision): clarify scope boundary for Gaussian basis support
test(schema): add round-trip serialization tests for QMatEntry
```

---

## Versioning Policy

QMatBridge follows [Semantic Versioning](https://semver.org/) from `0.1.0`.

| Change type | Version bump |
| --- | --- |
| New adapter or exporter (backward-compatible) | `patch` |
| New optional field on a dataclass | `patch` |
| Rename or remove a field on `QMatEntry` | **`minor`** + migration note |
| Change to canonical hash algorithm | **`minor`** + CHANGELOG entry |
| Change to a public function signature | **`minor`** |
| Incompatible API change (post v1.0) | **`major`** |

All changes that bump the minor or major version require a `CHANGELOG.md` entry
and explicit maintainer sign-off. See [GOVERNANCE.md](GOVERNANCE.md) for the
decision-making process.
