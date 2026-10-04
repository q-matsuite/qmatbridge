# Integrations plan

How QMatBridge grows from "Materials Project in, JSON out" to a bridge between many
databases and many quantum toolchains. Status: **proposal** — items marked *(decision)*
need a public Discussion before work starts, as GOVERNANCE.md requires for schema changes.

## Principles

1. **The NIR stays framework-neutral.** `QMatEntry` knows nothing about OpenFermion, qualtran
   or any database client. Integrations live at the edges.
2. **Integrations are plugins.** An adapter or exporter is a small class registered through an
   entry point; the core never imports third-party packages.
3. **Optional dependencies only.** Core stays dependency-free; each integration is an extra.
4. **Provenance survives every hop.** An exporter records what it produced in
   `ExportMetadata`, tied to the entry's `canonical_hash()`.
5. **Golden-file tests.** Each integration ships fixtures and asserts exact outputs. Unit tests
   never touch the network; live tests are marked `integration` and run on a schedule.

## Where we are

| Area | State |
| --- | --- |
| Source: Materials Project | Implemented (structure, plane-wave Hamiltonian metadata); validated against the live API for LiCoO₂, Si/GaN pending the data run |
| Source: OQMD | Stub |
| Source: OPTIMADE, Alexandria | Not started |
| Exporters | None |
| Resource estimation | None |
| Release | Not on PyPI; no DOI |

## Gaps that block exporters

An exporter that builds a first-quantized plane-wave Hamiltonian needs more than the NIR holds today:

- **Atomic positions.** `StructureMetadata` stores species and lattice but not site coordinates.
  (The landing-page data carries them separately, so the information is reachable but not in the schema.)
- **Valence charges** per species, i.e. which pseudopotential valence the electron count assumes.
- **Reading entries back.** `qmatbridge.io` writes JSON but cannot load it (issue: `read_entry_json`),
  so fixtures can't feed an exporter test.
- **A plugin contract**, so integrations don't each invent their own call shape.

## Milestones

### M1 — Finish v0.2 and release
Generate and commit the Tier-1 fixtures (Si, GaN, LiCoO₂), run the integration tests, fix what the
live API reveals, merge the site, bump to 0.2.0, publish to PyPI with trusted publishing, add a Zenodo DOI.
*Acceptance:* `pip install qmatbridge[mp]` works from PyPI; `fetch_entry_from_mp("mp-149")` runs in CI nightly.

### M2 — Schema v0.2 *(decision)*
Additive, non-breaking where possible:
- `SiteMetadata` (element, fractional coordinates) and `StructureMetadata.sites`, default empty.
- Per-species valence charges, in `HamiltonianMetadata` or in the pseudopotential record.
- `from_dict` / `read_entry_json` that rejects unknown `schema_version` with a clear error.
- **Hash policy:** adding positions to `canonical_hash()` would change every existing hash. Options:
  version the hash (`hash_version`), include positions only when present, or leave the hash
  unchanged and hash positions separately. Decide in the Discussion; migration note required.
*Acceptance:* round-trip test `from_dict(to_dict(e)).canonical_hash() == e.canonical_hash()`; fixtures regenerated.

### M3 — Plugin contract
```python
class Adapter(Protocol):
    name: str
    def fetch_entry(self, identifier: str, **options) -> QMatEntry: ...

class Exporter(Protocol):
    name: str
    def export(self, entry: QMatEntry, **options) -> ExportMetadata: ...
```
Entry-point groups `qmatbridge.adapters` and `qmatbridge.exporters`; `qmatbridge.registry` lists
what is installed. Migrate the Materials Project adapter onto it.
*Acceptance:* a third-party package can register an adapter with no change to this repo.

### M4 — More sources
1. **OPTIMADE** first: one implementation reaches many providers (the README lists AFLOW, JARVIS,
   NOMAD, MC3D). Needs provider-specific handling of what each exposes about the calculation.
2. **OQMD** live fetch.
3. **Alexandria** if licences and formats permit.
Each source documents its licence and key requirements (see the bring-your-own-keys docs in PR #9).
*Acceptance:* each adapter has recorded-response unit tests and a scheduled live test.

### M5 — Exporters
1. **Raw plane-wave arrays** (NumPy): G-vectors, kinetic term, structure factors. No heavy dependency.
2. **OpenFermion** export of the corresponding operator.
3. **qualtran / pyLIQTR** hooks for LCU coefficients and oracle metadata.
*Before designing 2 and 3, verify the current public APIs of those libraries; I have not.*
*Acceptance:* each exporter reproduces a published or analytically known number on a small system
(e.g. total G-vector count against `qmatbridge.basis`), recorded in `ExportMetadata`.

### M6 — Resource estimation (roadmap v0.5)
T/Toffoli and qubit estimates from `OracleMetadata`, delegating to qualtran or pyLIQTR rather than
reimplementing them. Estimates are labelled with the method, assumptions and the entry hash.

## Cross-cutting

- **Scheduled integration CI:** a nightly workflow runs `pytest -m integration` using a repository
  secret for `MP_API_KEY`; failures open an issue. Never runs on fork PRs.
- **Release automation:** tag → build → PyPI trusted publishing → GitHub release; CHANGELOG-driven notes.
- **Docs:** one how-to per adapter and exporter; an "Add an adapter" guide using the M3 contract.
- **Licences and keys:** every data source's terms are recorded in `docs/adapters.md`.

## Open questions

- Hash policy for positions (M2).
- Where valence charges live (M2).
- Whether OPTIMADE entries can carry enough calculation metadata to build a Hamiltonian at all (M4).
- Which first-quantized formulation the exporters target first (M5).

## Issue map

| Milestone | Issue |
| --- | --- |
| M1 Finish v0.2 and release | #12 |
| M2 Schema v0.2 | #13 (Discussion #24), #14 `read_entry_json` |
| M3 Plugin contract | #15 |
| M4 Sources | #16 OPTIMADE, #17 OQMD |
| M5 Exporters | #18 raw arrays, #19 OpenFermion, #20 qualtran / pyLIQTR |
| Cross-cutting | #21 scheduled integration CI, #22 PyPI + Zenodo |
| M6 Resource estimation | #23 |
