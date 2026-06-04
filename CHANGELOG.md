# Changelog

All notable changes to QMatBridge are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Breaking changes to `QMatEntry` or its nested schema classes are marked
**[BREAKING]** and accompanied by a migration note.

---

## [Unreleased]

---

## [0.1.0] — 2026-06-03

Initial repository scaffold and schema definition.  First release prepared for PyPI.

### Added

**Core schema (`qmatbridge/schema.py`)**
- `ExternalIdentifier` — single database identifier with optional URL
- `SourceProvenance` — upstream database source, functional, pseudopotential,
  DFT code, and retrieval timestamp
- `LatticeMetadata` — Bravais lattice parameters (lengths, angles, spacegroup)
- `StructureMetadata` — chemical formula, site count, species, lattice
- `BasisMetadata` — plane-wave / Gaussian / LCAO basis specification
- `TermMetadata` — per-physical-term LCU norms, coefficient labels, and
  implementation notes
- `OracleMetadata` — SELECT/PREPARE oracle type, index encoding, coefficient
  sampling scheme, and annotated complexity dict
- `ExportMetadata` — downstream export record with target name and status
- `MaterialReference` — provenance + structure
- `HamiltonianMetadata` — electrons, spin, basis, terms, oracle
- `QMatEntry` — top-level NIR with `to_dict()` and `canonical_hash()`

**I/O (`qmatbridge/io.py`)**
- `to_dict(obj)` — recursive dataclass-to-dict conversion; tuples → lists
- `write_entry_json(entry, path, indent=2)` — UTF-8 JSON export with parent
  directory creation and trailing newline

**Adapters (stubs)**
- `qmatbridge.adapters.materials_project` — `MPAdapterConfig`,
  `build_material_reference_from_mp`, `fetch_structure_metadata_from_mp`
  (stub), `fetch_hamiltonian_metadata_from_mp` (stub)
- `qmatbridge.adapters.oqmd` — `OQMDAdapterConfig`,
  `build_material_reference_from_oqmd`, `fetch_structure_metadata_from_oqmd`
  (stub), `fetch_hamiltonian_metadata_from_oqmd` (stub)

**Tests**
- `tests/unit/test_schema.py` — instantiation, canonical hash stability and
  sensitivity, serialization round-trip (28 tests)
- `tests/unit/test_io.py` — `to_dict` conversion rules, `write_entry_json`
  file I/O (22 tests)

**Examples**
- `examples/minimal_entry.py` — fully populated silicon `QMatEntry` (mp-149,
  plane-wave basis, LCU oracle, term breakdown)

**Documentation**
- `docs/vision.md` — design rationale, scope, governance principles
- `docs/adapters.md` — Materials Project, OQMD, OPTIMADE, Alexandria
- `docs/oracle-model.md` — term decompositions, SELECT/PREPARE, sparse access,
  index encoding, complexity annotations

**Governance and community files**
- `CONTRIBUTING.md`, `GOVERNANCE.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  `SUPPORT.md`
- `.github/ISSUE_TEMPLATE/` — bug report and feature request YAML templates
- `.github/PULL_REQUEST_TEMPLATE.md`

**CI**
- `.github/workflows/python-package.yml` — ruff, mypy, pytest on
  Python 3.10, 3.11, 3.12

**Planning**
- `planning/initial_issues.md` — ten scoped GitHub issues for v0.1–v0.4

[Unreleased]: https://github.com/rmsreis/qmatbridge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rmsreis/qmatbridge/releases/tag/v0.1.0
