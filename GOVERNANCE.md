# Governance

This document describes how QMatBridge is governed, how decisions are made,
and how the project is expected to evolve as the community grows.

---

## Guiding Principles

- **Scientific integrity** — decisions prioritize correctness, reproducibility,
  and alignment with the physics and quantum-computing literature.
- **Openness** — all technical discussions happen in public GitHub issues or
  Discussions; no decisions are made in private channels.
- **Consensus over speed** — we prefer slow, deliberate decisions on core
  interfaces over fast, breaking ones.
- **Welcoming to newcomers** — career stage and institutional affiliation carry
  no weight in technical discussions.

---

## Roles

### Maintainer

Maintainers have commit access to the repository and are responsible for:

- Reviewing and merging pull requests
- Triaging issues and Discussions
- Cutting releases and updating `CHANGELOG.md`
- Enforcing the [Code of Conduct](CODE_OF_CONDUCT.md)
- Stewarding the technical direction of the project

**Current maintainers:**

| Name | GitHub | Affiliation |
| --- | --- | --- |
| Roberto Reis | [@rmsreis](https://github.com/rmsreis) | — |

New maintainers are nominated by an existing maintainer and confirmed by
consensus of all current maintainers. There is no fixed term; maintainers
who are no longer active are asked to step back gracefully and are listed
in the Emeritus section below.

### Contributor

Anyone who has had a pull request merged, filed a validated bug report, or
made a substantive contribution to documentation or benchmarks is a
Contributor. Contributors are listed in the repository's GitHub
contributor graph and in release notes.

Contributors may be nominated to become maintainers after demonstrating
sustained, high-quality engagement with the project.

### Community Member

Anyone who participates in Discussions, opens issues, or engages
constructively with the project is a Community Member. No formal role
assignment is required.

---

## Decision-Making Process

### Routine decisions

Routine decisions (bug fixes, documentation, adding adapters or exporters that
do not alter the public schema, CI improvements) are made by any maintainer
after a standard pull-request review cycle.

### Significant decisions

Significant decisions include:

- Changes to the public schema (`QMatEntry`, `MaterialReference`, `HamiltonianMetadata`)
- New optional extras that add heavy dependencies
- Changes to the canonical hash algorithm
- Release of a new minor or major version
- Addition or removal of a maintainer

These require:

1. An open GitHub issue or Discussion tagged `governance` or `schema`
2. A minimum **7-day open comment period**
3. Explicit approval from at least **one maintainer** (two, once there are three
   or more maintainers)
4. No unresolved blocking objections from active contributors

If consensus cannot be reached, the lead maintainer has a casting vote, with a
written rationale posted publicly in the issue thread.

### Blocking objections

A blocking objection must be technical or scientific in nature and accompanied
by a concrete alternative proposal. Process objections (e.g., "this was
decided too fast") are valid; personal preference objections without
justification are not.

---

## Releases

Releases follow [Semantic Versioning](https://semver.org/). The release
process is:

1. Maintainer opens a release PR updating `pyproject.toml` version,
   `CHANGELOG.md`, and any migration notes.
2. At least one other maintainer reviews (once two or more maintainers exist).
3. Tag is pushed; CI publishes to PyPI automatically.

Pre-release versions (`0.x.y`) may have faster iteration. The first `1.0.0`
release signals a stable, supported public API.

---

## Roadmap and Prioritization

The project roadmap lives in `README.md`. Maintainers review and update it
at each minor release. Community members may propose roadmap items via
GitHub Discussions; inclusion is at maintainer discretion aligned with the
[project vision](docs/vision.md).

---

## Funding and Institutional Affiliation

QMatBridge is an independent open-source project. Any future grant funding
(NSF, DOE, or otherwise) will be disclosed in this document, along with any
affiliated institutions and the scope of their involvement. Funding does not
confer governance rights beyond those described above.

---

## Advisory Role (Future)

As the project matures and the contributor base grows, we anticipate forming
a Scientific Advisory Board drawn from the quantum-computing, materials science,
and fault-tolerant algorithms communities. The advisory board will provide
technical guidance but will not hold formal governance power. Details will be
added to this document when that structure is established.

---

## Amendments

Changes to this document follow the significant-decision process above, with a
minimum 14-day comment period.

---

## Emeritus Maintainers

*None yet.*
