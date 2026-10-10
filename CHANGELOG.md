# Changelog

All notable changes to QMatBridge are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Breaking changes to `QMatEntry` or its nested schema classes are marked
**[BREAKING]** and accompanied by a migration note.

---

## [Unreleased]

---

## [0.5.0] — 2026-10-09

The generic OPTIMADE adapter. Nothing here changes any `canonical_hash()` value or the schema.

### Added
- **Generic OPTIMADE adapter** (registry name `optimade`): `fetch_entry_from_optimade`,
  `fetch_structure_metadata_from_optimade`, `fetch_hamiltonian_metadata_from_optimade`, plus the pure
  converters `structure_from_optimade_doc` and `hamiltonian_from_optimade`. Reads the standard
  `/v1/structures/{id}` endpoint, so it covers Alexandria, the Materials Project and other OPTIMADE
  servers (`KNOWN_PROVIDERS`, or any `base_url`). OPTIMADE returns no calculation settings, so the
  cutoff (required), spin treatment and valence charges are configured and listed under
  `hamiltonian.metadata["assumed"]`. Disordered, vacancy-bearing and non-periodic structures are
  refused. Standard-library HTTP; no dependency. Checked live against the Materials Project and
  Alexandria; the OQMD server still returned HTTP 502, so its live check remains owed.

---

## [0.4.0] — 2026-10-07

Schema 0.3 (per-species valence charges), the OQMD adapter, and the first exporter. Nothing here
changes any `canonical_hash()` value.

### Added
- **Schema 0.3: `HamiltonianMetadata.valence_charges`** (element → valence electrons contributed
  by the pseudopotential; default empty), decided in #13. `schema_version` defaults to `"0.3"`;
  readers accept `"0.1"`, `"0.2"` and `"0.3"`. Not part of `canonical_hash()`. New
  `QMatEntry.valence_electron_total()` and `check_electron_count()` verify the charges against
  `num_electrons` over the recorded sites.
- The Materials Project adapter reads charges from the task's `potcar_spec` and `ZVAL`; it leaves
  them empty rather than guess when they are absent, mismatched or inconsistent with `NELECT`.
- **OQMD adapter** (registry name `oqmd`): `fetch_entry_from_oqmd`, `fetch_structure_metadata_from_oqmd`,
  `fetch_hamiltonian_metadata_from_oqmd`, plus the pure converters `structure_from_oqmd_doc` and
  `hamiltonian_from_oqmd`. Standard-library HTTP with retries; no dependency. OQMD does not publish
  cutoff, spin treatment or electron count, so those are configured and listed under
  `hamiltonian.metadata["assumed"]`; elements without an unambiguous PAW valence count must be
  supplied (#17). Tested against recorded-shape responses only: the OQMD server returned HTTP 502
  during development, so a live check is still owed.
- **`numpy_planewave` exporter** (registry name; `pip install qmatbridge[numpy]`): writes G-vectors,
  Miller indices, kinetic energies, ion positions and charges and the ionic structure factor to an
  `.npz`. The plane-wave set matches `BasisMetadata.num_plane_waves` exactly. Refuses entries
  without positions or consistent valence charges (#18).
- `docs/stack.md`: which parts of the stack are open and where a private extension plugs in.

### Removed
- The empty-in-practice `oqmd` extra (`qmpy-rester`): the adapter needs no dependency.

### Changed
- Entries written by this version carry `schema_version: "0.3"`, which 0.3.x readers reject with a
  clear error. The committed fixtures and the website data were rewritten at 0.3 with empty charges.

---

## [0.3.0] — 2026-10-06

Schema 0.2: atomic positions, and a fingerprint that covers them. **[BREAKING] for stored
hashes of freshly fetched entries** (details under *Changed*). The roadmap is renumbered so that
this schema work is v0.3; the OPTIMADE/OQMD/Alexandria adapters move to v0.4, exporters to v0.5 and
resource estimation to v0.6.

### Added
- **Schema 0.2: atomic positions.** `SiteMetadata` (element and fractional coordinates) and
  `StructureMetadata.sites` (default empty). `schema_version` defaults to `"0.2"`; readers accept
  `"0.1"` and `"0.2"`. The Materials Project adapter now records positions, and the Tier-1
  fixtures and the website carry them.
- `canonical_hash()` covers the lattice parameters and the positions **when `sites` is non-empty**
  (Discussion #24, option B): fixed 6-decimal strings, coordinates wrapped into [0, 1), sites
  sorted. Python and the website's JavaScript produce identical hashes (tested by running the
  site's actual script under Node, including exact rounding ties such as 1/128).

### Changed
- **Hashes of freshly fetched entries change.** They now include positions, so
  `fetch_entry_from_mp("mp-149").canonical_hash()` differs from 0.2.x. Entries *without* `sites`,
  including every entry stored by 0.2.x, keep exactly their old hash (verified for the six Tier-1
  materials against the published values). Anyone who stored 0.2.x hashes next to freshly fetched
  entries should re-fetch, or compare with `sites` cleared.
- A lattice 50% larger no longer collides with the original for entries that record positions.
- The fixture builder takes positions from the entry instead of making a second API call.
- **Forward compatibility.** Entries written by 0.3.0 carry `schema_version: "0.2"`, which 0.2.x
  readers reject with a clear `unsupported schema_version` error. 0.3.0 reads both `"0.1"` and `"0.2"`.
- Roadmap renumbered in the README, docs and website (see above).
- `CITATION.cff` and the README now carry the Zenodo concept DOI `10.5281/zenodo.23192772`
  (the 0.2.1 archive is `10.5281/zenodo.23192773`).

### Fixed
- The release workflow is safe to retry: PyPI upload skips files that already exist (#40).

---

## [0.2.1] — 2026-10-06

Hardening release: fixes the defects found by stress-testing 0.2.0, corrects the author's name and
adds the affiliation, and adds three Tier-1 materials. No schema change (`schema_version` stays
`0.1`) and no change to any `canonical_hash()` value: entries and hashes from 0.2.0 remain valid.
This is the first release archived on Zenodo with the corrected author metadata.

Hardening from a stress test of the published 0.2.0 (install matrix on Python 3.10, 3.12, 3.13 and
3.14, 27 live Materials Project materials, hostile-input and property-based fuzzing).

### Fixed
- **`write_entry_json` could destroy an existing file.** A failure part-way through serialisation
  left the previous good file truncated. It now serialises first and replaces the file atomically,
  and refuses NaN/Infinity (which are not valid JSON) with a clear `ValueError`.
- **Unbounded work in `num_plane_waves_exact`.** A huge cutoff or cell (for example `ENCUT = 1e12`)
  ran effectively forever. It now refuses, in milliseconds, anything beyond `max_candidates`
  (default 50 million, about 15 s; configurable, `None` disables) and points to `method="estimate"`.
  Non-finite or non-positive lengths and cutoffs, angles outside (0, 180) and overflowing cells now
  raise `ValueError` instead of `OverflowError` / `ZeroDivisionError`.
- **`entry_from_dict` was ~30x slower than necessary** on entries with many nested objects: type
  hints were re-resolved per object. Decoding 200,000 terms took 129 s; it now takes about 4 s.
- **`read_entry_json` leaked non-`EntryFormatError` exceptions** for hostile files
  (`UnicodeDecodeError`, `RecursionError`, over-long integers) and accepted `NaN` / `Infinity`.
  All are now `EntryFormatError`; a UTF-8 BOM is tolerated; non-finite floats are rejected anywhere
  in an entry.
- **Materials Project converters** (`structure_from_mp_doc`, `hamiltonian_from_mp_task_doc`,
  `functional_from_mp_task_doc`) leaked `TypeError`, `KeyError`, `AttributeError` and
  `OverflowError` for malformed documents and accepted NaN, infinite, negative or zero lattice
  constants and zero or negative electron counts. Every malformed input is now a `ValueError`.
- **Packaging:** the wheel now ships `py.typed`, so downstream type checkers use the annotations.
  The `[mp]` extra is restricted to Python 3.11+ (on 3.10 pip installed an `emmet-core` whose import
  fails), and the adapter's `ImportError` now shows the underlying error and the Python-version hint.
  Python 3.13 and 3.14 are added to the classifiers and the CI matrix (both were tested manually).
- **Docs:** the getting-started "Read an entry back" example raised `NameError`; the
  `canonical_hash()` docstring omitted `functional` from its list of hashed fields; and the hash was
  described as covering "the physics". It covers eleven setup fields and **not** the lattice, atomic
  positions, species or pseudopotential; the guide, README, vision page and website now say so.

### Added
- Landing page visual pass: an interactive **anatomy of an entry** (real values for the selected material, with the fingerprint-covered fields marked), a **"two groups, one silicon"** illustration built from fingerprints computed in the browser, a horizontal **roadmap** with corrected statuses (v0.2 is released), and a dynamic example count.
- Three more Tier-1 materials, fetched live and validated against the spec: LiFePO₄ (a 28-atom cathode), NaCl and BaTiO₃. The original three keep their hashes.
- Property-based tests (`tests/property/`, `hypothesis` in the `dev` extra): reader, round trip,
  hash invariants, MP converters and plane-wave counting. Regression tests for every fix above
  (`tests/unit/test_hardening.py`) and a test that runs the documentation's code examples.

### Changed
- Install notes (README, website, org profile, release guide) now say `pip install qmatbridge`
  installs the latest release from PyPI; the website's install section shows the PyPI commands.
- Author credited as Roberto dos Reis (the family name is "dos Reis") with affiliation q-matsuite in
  `CITATION.cff`, the BibTeX (README and website), the credit lines, `pyproject.toml`, GOVERNANCE and
  SECURITY. New `.zenodo.json` sets the metadata of Zenodo archive records; a test keeps the citation
  files and the package version in sync.
- Author credited as Roberto dos Reis with the affiliation Department of Materials Science and Engineering,
  Northwestern University (Evanston, IL), linked to https://www.robertodosreis.com, in `CITATION.cff`,
  `.zenodo.json`, the credit lines, and the website. `LICENSE` now reads "Roberto dos Reis" (it was
  "Roberto Reis"). q-matsuite remains the organisation in the BibTeX and the project pages.

---

## [0.2.0] — 2026-10-05

First release with a working Materials Project adapter. Install from PyPI with
`pip install qmatbridge`; the `[mp]` extra (`mp-api`, `pymatgen`) needs Python 3.11+ in practice.
The data model is unchanged (`schema_version` stays `0.1`; same fields, same `canonical_hash()`
algorithm), so entries and hashes from 0.1.0 remain valid.

Highlights: live Materials Project fetching validated for Si, GaN and LiCoO₂; plane-wave counting;
reading entries back from JSON; a plugin registry for adapters and exporters; Tier-1 fixtures with
nightly drift checks; documentation and a landing page at https://q-matsuite.com/qmatbridge/.

### Added
- `qmatbridge.registry`: `Adapter` and `Exporter` protocols, lazy discovery through the
  `qmatbridge.adapters` / `qmatbridge.exporters` entry-point groups, `list_adapters`,
  `get_adapter`, `list_exporters`, `get_exporter`, and `PluginError` / `UnknownPluginError`.
  The Materials Project adapter is now the `MaterialsProjectAdapter` plugin. See
  "Writing a plugin" in the docs (#15).
- Scheduled live integration tests (`.github/workflows/integration.yml`, `tests/integration/`):
  nightly spec and drift checks of the Tier-1 materials against the live Materials Project API;
  opens/closes an `integration-failure` issue; skips cleanly until the `MP_API_KEY` secret exists.
  New "How the workflows work" guide (#21).
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
  `fetch_entry_from_mp` (lazy `mp-api` import). Unit-tested with a fake client and validated
  against the live API for Si, GaN and LiCoO₂ (nightly via `pytest -m integration`).
- Tier-1 benchmark specification (`benchmarks/tier1.py`) and a fixture builder
  (`benchmarks/build_tier1_fixtures.py`) that validates live MP data before writing.
- MkDocs documentation site (`mkdocs.yml`, getting-started, API reference) and a
  GitHub Pages deploy workflow.
- `CITATION.cff`; CI jobs for docs build and distribution build; 85 % coverage floor.
- `docs` optional extra.
- Landing page (`website/`, `tools/build_site.py`) with an interactive examples
  explorer; Tier-1 examples are now Si, GaN and LiCoO₂ (battery cathode).
- `functional_from_mp_task_doc` — records `PBE+U` for GGA+U calculations.
- Release automation (`.github/workflows/release.yml`, `tools/release_info.py`): tag-driven build,
  tag/version check, wheel smoke test, PyPI trusted publishing, and a GitHub release with notes
  from this file; dry run to TestPyPI. Dependabot keeps GitHub Actions current. See "Releasing"
  in the docs (#22).

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
- Docs, README and website no longer say QMatBridge is not on PyPI: 0.1.0 was published on
  2026-06-04. The install notes now say that 0.1.0 predates the v0.2 features. The "needs
  mp-api" error message gives an install command that is correct from source and from PyPI.

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

[Unreleased]: https://github.com/q-matsuite/qmatbridge/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/q-matsuite/qmatbridge/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/q-matsuite/qmatbridge/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/q-matsuite/qmatbridge/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/q-matsuite/qmatbridge/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/q-matsuite/qmatbridge/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/q-matsuite/qmatbridge/releases/tag/v0.1.0
