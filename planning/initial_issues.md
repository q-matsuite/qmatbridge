# QMatBridge — Initial GitHub Issue Set

Thirteen scoped issues for the first public milestone of QMatBridge.
Copy each block into a GitHub issue; suggested labels and milestone are
included for each.

---

> **Note:** these were drafted before the repo went public and were never filed as GitHub
> issues. The live work items are tracked in [`integrations.md`](integrations.md) (issues #12–#23).
> Items 10 and 13 here correspond to #19 and #14.

## Status (updated for v0.2 work)

| Issue | State |
| --- | --- |
| 3 — MP live fetch | Implemented; live-API validation tracked in Issue 11 |
| 5 — Tier-1 family | Spec in `benchmarks/tier1.py`; table corrected |
| 6 — Tier-1 fixtures | Builder done; fixtures need an MP key (Issue 12) |
| 9 — MkDocs site | Done (`mkdocs.yml`, Pages workflow) |
| 1, 2, 4, 7, 8, 10 | Open |

---

## Issue 1 — Schema: finalize TermMetadata coefficient representation

**Title:** `[schema] Finalize TermMetadata coefficient labels and norm conventions`

**Rationale:**
`TermMetadata` currently stores `lambda_one_norm` and `lambda_spectral` as
bare floats.  Before v0.1 is declared stable, we need to agree on:
- whether coefficient labels are stored at the term level or globally
- whether norms are always in Hartree or whether units must be declared
- whether `truncation_threshold` belongs here or in `BasisMetadata`

This is a blocking schema decision because any change after the first release
requires a minor-version bump and a migration note.

**Proposed tasks:**
- [ ] Survey two or three published resource-estimation papers (Babbush 2019,
  Berry 2019, Su 2021) for the coefficient/norm conventions they use
- [ ] Propose a concrete field layout in a GitHub Discussion under
  `schema` tag
- [ ] Update `schema.py` and `docs/oracle-model.md` to match
- [ ] Add a round-trip test confirming that a `TermMetadata` instance
  serializes and deserializes correctly with all new fields

**Labels:** `schema`, `discussion`, `v0.1`
**Milestone:** v0.1 — Schema & Scaffold

---

## Issue 2 — I/O: JSON export stability and round-trip tests

**Title:** `[io] Add JSON round-trip tests and stabilize silicon_entry.json format`

**Rationale:**
`qmatbridge.io.write_entry_json` exists but has no automated tests verifying
that the written JSON is schema-stable across patch releases.  Before the
first PyPI release we need a regression fixture and a formal round-trip test
so that accidental schema drift is caught in CI.

**Proposed tasks:**
- [ ] Commit `silicon_entry.json` as a checked-in fixture (currently in
  `.gitignore`) and document its role
- [ ] Add `tests/unit/test_io.py` with:
  - `test_write_entry_json_creates_file`
  - `test_to_dict_round_trip` (serialize → deserialize → compare)
  - `test_canonical_hash_stable_across_write` (hash unchanged after write)
- [ ] Add a CI step that regenerates `silicon_entry.json` and fails if it
  differs from the committed fixture
- [ ] Document the stability guarantee in `CHANGELOG.md` under v0.1

**Labels:** `io`, `testing`, `v0.1`
**Milestone:** v0.1 — Schema & Scaffold

---

## Issue 3 — Adapter: implement Materials Project live fetch (v0.2)

**Title:** `[adapter][mp] Implement fetch_structure_metadata_from_mp via mp-api`

**Rationale:**
The Materials Project adapter stub exists at
`qmatbridge/adapters/materials_project.py` with `fetch_structure_metadata_from_mp`
raising `NotImplementedError`.  This is the primary v0.2 deliverable and
unlocks real DFT data for all downstream consumers.

**Proposed tasks:**
- [ ] Implement `fetch_structure_metadata_from_mp` using `MPRester` from
  `mp-api>=0.41`:
  - lattice parameters and volume
  - site positions and species
  - spacegroup number and symbol
- [ ] Implement `fetch_hamiltonian_metadata_from_mp`:
  - VASP ENCUT from task document
  - k-point mesh from `kpoints` sub-document
  - pseudopotential family from `potcar_symbols`
- [ ] Add `num_plane_waves_from_ecut(ecut_ev, volume_ang3)` utility
- [ ] Add `tests/integration/test_adapter_mp.py` marked
  `@pytest.mark.integration`, skipped when `MP_API_KEY` is not set
- [ ] Verify the silicon (mp-149) round-trip produces the expected
  `canonical_hash`

**Labels:** `adapter`, `materials-project`, `v0.2`
**Milestone:** v0.2 — Materials Project Adapter

---

## Issue 4 — Adapter: OPTIMADE integration planning and interface design

**Title:** `[adapter][optimade] Design and stub the OPTIMADE adapter interface`

**Rationale:**
A single OPTIMADE-compliant adapter would cover AFLOW, JARVIS, NOMAD, MC3D,
and other databases.  Before writing any fetcher code, the interface should
be agreed upon and stubbed so that community contributors can implement
individual provider wrappers without breaking the shared contract.

**Proposed tasks:**
- [ ] Read the OPTIMADE v1.2 spec for `/structures/{id}` response shape
- [ ] Add `qmatbridge/adapters/optimade.py` with:
  - `OptimadeAdapterConfig` (base_url, api_key, provider)
  - `build_material_reference_from_optimade(entry_id, base_url, ...)`
  - `fetch_structure_metadata_from_optimade(entry_id, base_url, ...)`
    (stub, raises `NotImplementedError`)
- [ ] Define the canonical `source` string convention for OPTIMADE providers
  (e.g., `"optimade:aflow"` vs `"aflow"`)
- [ ] Add provider URL table to `docs/adapters.md`
- [ ] Open a separate issue for each provider's live implementation

**Labels:** `adapter`, `optimade`, `v0.3`, `design`
**Milestone:** v0.3 — OPTIMADE + Alexandria Adapters

---

## Issue 5 — Benchmarks: define Tier-1 canonical benchmark family

**Title:** `[benchmarks] Define and document the Tier-1 canonical benchmark material set`

**Rationale:**
`benchmarks/README.md` lists a proposed Tier-1 set (Si, LiH, Fe, MgO, TiO₂)
but no formal selection criteria are documented.  Before populating the set
with real entries, we need criteria that any future material must satisfy to
be added.

**Proposed tasks:**
- [ ] Draft selection criteria:
  - open-access DFT data available (MP, OQMD, or published)
  - known experimental ground-state energy for validation
  - spans at least three crystal systems (cubic, hexagonal, non-cubic)
  - includes at least one magnetic/spin-polarized example
- [ ] Write the criteria into `benchmarks/README.md` under a new
  "Selection criteria" section
- [ ] Assign an MP/OQMD ID to each Tier-1 material and record it in the
  table
- [ ] Add a `benchmarks/tier1_materials.json` file listing the IDs and
  criteria met by each entry

**Labels:** `benchmarks`, `documentation`, `v0.2`
**Milestone:** v0.2 — Materials Project Adapter

---

## Issue 6 — Benchmarks: assemble first canonical material set as QMatEntry fixtures

**Title:** `[benchmarks] Generate and commit QMatEntry JSON fixtures for all Tier-1 materials`

**Rationale:**
Once Issue 5 defines the Tier-1 set and Issue 3 implements live MP fetching,
we can generate canonical `QMatEntry` JSON fixtures for each material.
These fixtures serve as reproducibility anchors: anyone can verify their
implementation against a known hash.

**Proposed tasks:**
- [ ] For each Tier-1 material, generate a `QMatEntry` via the MP adapter
  and write to `benchmarks/fixtures/<mp_id>.json`
- [ ] Commit the canonical hashes to `benchmarks/tier1_hashes.txt`
- [ ] Add a CI test that regenerates hashes and asserts no drift
- [ ] Document the fixture format in `benchmarks/README.md`
- [ ] Tag the fixtures with `schema_version: "0.1"` and include a note
  that they will be regenerated at each minor version bump

**Labels:** `benchmarks`, `data`, `v0.2`
**Milestone:** v0.2 — Materials Project Adapter

---

## Issue 7 — Schema: oracle metadata conventions for SELECT/PREPARE

**Title:** `[schema] Establish and document oracle_type and index_encoding conventions`

**Rationale:**
`OracleMetadata` now has `oracle_type` and `index_encoding` fields, but their
allowed values are not formally enumerated or validated.  Different research
groups use inconsistent terminology (SELECT vs PREPARE vs walk operator).
We should define the canonical vocabulary before v0.1 is locked.

**Proposed tasks:**
- [ ] Survey terminology across at least three papers:
  Babbush (2019), Berry (2019), Su (2021)
- [ ] Propose a controlled vocabulary for `oracle_type` and
  `index_encoding` in a GitHub Discussion tagged `schema`
- [ ] Add a `_ORACLE_TYPES` and `_INDEX_ENCODINGS` module-level set to
  `schema.py` documenting valid values (no runtime validation yet)
- [ ] Update `docs/oracle-model.md` tables with the agreed vocabulary
- [ ] Add one test asserting that the silicon example uses a recognised
  `oracle_type` value

**Labels:** `schema`, `oracle`, `discussion`, `v0.1`
**Milestone:** v0.1 — Schema & Scaffold

---

## Issue 8 — Docs: contributor guide improvements (adapter and exporter how-tos)

**Title:** `[docs] Add step-by-step adapter and exporter how-to guides to CONTRIBUTING.md`

**Rationale:**
`CONTRIBUTING.md` has skeleton sections for adding adapters and exporters
but they are minimal.  A contributor who wants to add, say, an AFLOW adapter
or an OpenFermion exporter needs a concrete worked example showing the full
path: config → stub → live fetch → test.

**Proposed tasks:**
- [ ] Add a full worked example for a minimal adapter (use a toy
  in-memory database, not a real API) to `CONTRIBUTING.md`
- [ ] Add a full worked example for a minimal exporter (output a plain
  numpy array) to `CONTRIBUTING.md`
- [ ] Document the `@pytest.mark.integration` pattern and how to skip
  tests without an API key
- [ ] Link from `docs/adapters.md` to the new sections
- [ ] Review and update the PR template to check "adapter checklist"
  and "exporter checklist" items

**Labels:** `documentation`, `contributor-experience`, `v0.1`
**Milestone:** v0.1 — Schema & Scaffold

---

## Issue 9 — Docs: set up MkDocs documentation site

**Title:** `[docs] Set up MkDocs + Material theme for hosted documentation`

**Rationale:**
All documentation currently lives as Markdown files in `docs/`.  For the
project to be usable by researchers who are not reading source code, we need
a rendered, searchable site.  MkDocs + Material is the standard choice for
Python scientific projects.

**Proposed tasks:**
- [ ] Add `mkdocs.yml` at the repo root with:
  - site name, repo URL, license
  - `nav` tree covering all current `docs/` pages
  - Material theme with dark mode toggle
- [ ] Add `mkdocs` and `mkdocstrings[python]` to `pyproject.toml`
  under a new `docs` optional extra
- [ ] Add a GitHub Actions workflow
  `.github/workflows/docs.yml` that builds and deploys to
  `gh-pages` on push to `main`
- [ ] Add auto-generated API reference from docstrings for
  `qmatbridge.schema` and `qmatbridge.io`
- [ ] Add the docs badge to `README.md`

**Labels:** `documentation`, `infrastructure`, `v0.2`
**Milestone:** v0.2 — Materials Project Adapter

---

## Issue 10 — Exporters: implement first downstream export path (OpenFermion)

**Title:** `[exporter][openfermion] Implement QMatEntry → OpenFermion InteractionOperator exporter`

**Rationale:**
`ExportMetadata` records exports but no actual exporter modules exist yet.
The OpenFermion `InteractionOperator` is the most widely used intermediate
representation in the quantum-chemistry / quantum-algorithms community and
makes a natural first export target.  Completing this closes the loop from
DFT database → `QMatEntry` → quantum compiler.

**Proposed tasks:**
- [ ] Add `qmatbridge/exporters/openfermion.py`:
  - `to_interaction_operator(entry: QMatEntry) -> "InteractionOperator"`
  - Must be importable without `openfermion` installed; guard with
    `try/except ImportError`
- [ ] Implement one-body (kinetic + electron-nuclear) and two-body
  (electron-electron Coulomb) integrals in the plane-wave basis using
  the Hamiltonian parameters in `HamiltonianMetadata`
- [ ] Add `tests/integration/test_exporter_openfermion.py` marked
  `@pytest.mark.integration` — compare eigenvalues against a reference
  for a small (LiH or H₂ in 4 plane waves) system
- [ ] Add `openfermion` to `pyproject.toml` optional extras
- [ ] Update `ExportMetadata.status` to `"complete"` in the example
  after a successful export
- [ ] Document usage in `examples/` and link from `docs/adapters.md`

**Labels:** `exporter`, `openfermion`, `v0.4`
**Milestone:** v0.4 — Hamiltonian Exporters

---

## Issue 11 — Adapter: validate Materials Project fetchers against the live API

**Title:** `[adapter] Validate fetch_entry_from_mp against live MP for Tier-1 materials`

**Rationale:**
The converters are unit-tested with representative documents and a fake client,
but the shapes of `summary.search`, `materials.search(calc_types)` and
`tasks.search` responses, and the presence of `input.parameters.NELECT` in task
documents, have not been confirmed against the production API.

**Proposed tasks:**
- [ ] Run `pytest -m integration` with `MP_API_KEY` set; fix any shape mismatches
- [ ] Confirm static-task selection picks the intended calculation
- [ ] Confirm electron counts match POTCAR valences for the Tier-1 set
- [ ] Add a scheduled (non-PR) CI job that runs the integration tests

**Labels:** `adapter`, `v0.2`

---

## Issue 12 — Benchmarks: generate and commit Tier-1 fixtures

**Title:** `[benchmarks] Generate Tier-1 QMatEntry fixtures via build_tier1_fixtures.py`

**Proposed tasks:**
- [ ] Verify the MP IDs in `benchmarks/tier1.py` (Si, LiH, Fe, MgO, TiO₂)
- [ ] Run `python benchmarks/build_tier1_fixtures.py` and review the output
- [ ] Commit `benchmarks/fixtures/*.json` and record each `canonical_hash()`

**Labels:** `benchmarks`, `v0.2`
**Depends on:** Issue 11, Issue 13

---

## Issue 13 — I/O: read entries back from JSON

**Title:** `[io] Add read_entry_json / from_dict for QMatEntry`

**Rationale:**
`qmatbridge.io` can write entries but not read them, so hash-regression tests on
committed fixtures cannot reconstruct an entry and recompute `canonical_hash()`.

**Proposed tasks:**
- [ ] Implement `from_dict` for the nested dataclasses and `read_entry_json`
- [ ] Reject unknown `schema_version` with a clear error
- [ ] Round-trip test: `from_dict(to_dict(e)).canonical_hash() == e.canonical_hash()`

**Labels:** `io`, `schema`, `v0.2`
