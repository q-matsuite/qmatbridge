# Changelog

All notable changes to QMatBridge are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Breaking changes to `QMatEntry` or its nested schema classes are marked
**[BREAKING]** and accompanied by a migration note.

---

## [Unreleased]

### Added
- `qmatbridge.io.read_entry_json`, `entry_from_dict`, `from_dict` and `EntryFormatError`: read entries
  back from JSON, the inverse of `write_entry_json`. Strict by design (unknown fields, missing
  fields, wrong types and unsupported `schema_version` are errors that name the field). The
  committed Tier-1 fixtures now load and reproduce the hashes shown on the website (#14).
- Tier-1 fixtures for Si, GaN and LiCoO₂ (`benchmarks/fixtures/`) and the landing-page data
  (`website/data/examples.json`), generated from the live Materials Project API; the first
  end-to-end validation of the MP fetchers against the real API.
- `qmatbridge.basis` — plane-wave counting: `cell_volume`, `cutoff_wavevector`,
  `num_plane_waves_estimate`, `num_plane_waves_exact`, `num_plane_waves_from_ecut`.
- Materials Project adapter: `structure_from_mp_doc` and
  `hamiltonian_from_mp_task_doc` (pure converters), plus live
  `fetch_structure_metadata_from_mp`, `fetch_hamiltonian_metadata_from_mp` and
  `fetch_entry_from_mp` (lazy `mp-api` import). Unit-tested with a fake client;
  **not yet validated against the live API** (`pytest -m integration`).
- Tier-1 benchmark specification (`benchmarks/tier1.py`) and a fixture builder
  (`benchmarks/build_tier1_fixtures.py`) that validates live MP data before writing.
- MkDocs documentation site (`mkdocs.yml`, getting-started, API reference) and a
  GitHub Pages deploy workflow.
- `CITATION.cff`; CI jobs for docs build and distribution build; 85 % coverage floor.
- `docs` optional extra.
- Landing page (`website/`, `tools/build_site.py`) with an interactive examples
  explorer; Tier-1 examples are now Si, GaN and LiCoO₂ (battery cathode).
- `functional_from_mp_task_doc` — records `PBE+U` for GGA+U calculations.

### Changed
- Landing page redesign: animated lattice hero, fingerprint images, scale comparison, and an
  interactive "Change one field, watch the fingerprint" demo that recomputes
  `canonical_hash()` in the browser (verified against the Python implementation).
- Repository URLs now point to `github.com/q-matsuite/qmatbridge` (org renamed from
  `QMatBridge`; GitHub redirects the old URLs). Site moves to `q-matsuite.com/qmatbridge/`.
- Generated example artifacts moved to `examples/outputs/`.
- Ruff: long lines allowed in `examples/` and `tests/`.

### Fixed
- Fixture builder requests the Materials Project run type named by each spec (`PBE`→`GGA`,
  `PBE+U`→`GGA+U`) instead of the adapter default, so LiCoO₂ is the +U calculation.
- Landing-page crystal viewer turns elongated cells (e.g. rhombohedral LiCoO₂) across the screen.
- MP adapter picked an arbitrary static calculation when a material had several
  (found live: LiCoO₂ came back as HSE06).  Selection is now by run type via
  `MPAdapterConfig.run_types` (default GGA / GGA+U), deterministic, and
  recorded in provenance (`candidate_task_ids`).
- Tier-1 spec: Materials Project calculations are always spin-polarized; the builder
  now also checks the functional.
- `python benchmarks/build_tier1_fixtures.py` failed with `No module named 'benchmarks'`
  when run by path; it now works that way and as a module, and a missing
  `MP_API_KEY` is a clean error (exit 2) instead of a traceback.
- Documented that the `[mp]` extra needs Python 3.11+ in practice: current `mp-api`
  depends on `emmet-core`, which imports `typing.NotRequired`.
- Corrected the Tier-1 benchmark table in `benchmarks/README.md` (electron counts
  now derived from MP POTCAR valences; cutoff column removed).

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

[Unreleased]: https://github.com/q-matsuite/qmatbridge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/q-matsuite/qmatbridge/releases/tag/v0.1.0
