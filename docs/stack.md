# Open core and private extensions

QMatBridge is MIT-licensed and stays that way. Parts of the wider stack may later be released
under different terms, so the boundary is drawn now, while it is cheap.

## The boundary

| Layer | Where it lives | Why |
| --- | --- | --- |
| Schema, `canonical_hash`, JSON I/O | this repository (MIT) | A shared format is only useful if everyone can read and write it. |
| Source adapters (Materials Project, OQMD, OPTIMADE, ...) | this repository (MIT) | Plumbing; its value is being interoperable. |
| Plain exporters (raw NumPy arrays, OpenFermion) | this repository (MIT) | Lets people verify the representation end to end. |
| **Contracts** for estimators and exporters (`Adapter`, `Exporter`, registry) | this repository (MIT) | The seam a private package plugs into. |
| Resource estimation, optimised oracle / LCU constructions, curated benchmark data, hosted services | **separate private package(s)** | Candidates for a later IP release. |

The v0.6 roadmap item ("resource estimation hooks") is therefore scoped here as the *hook*:
the interface and the `ExportMetadata` / `OracleMetadata` fields that carry a result. The
estimation algorithms themselves are not committed to this repository.

## How a private package attaches

It needs nothing from this repository beyond the public contracts. In the private package:

```toml
[project]
name = "qmatbridge-private"            # any name; not published to PyPI
dependencies = ["qmatbridge>=0.4"]

[project.entry-points."qmatbridge.exporters"]
lcu_estimate = "qmatbridge_private.estimate:LCUEstimator"
```

After `pip install` from the private index or repository, `get_exporter("lcu_estimate")` works
exactly like a built-in, and the result is an ordinary `ExportMetadata` on the entry. Listing is
lazy and names are unique (see [Writing a plugin](plugins.md)), so the public library never
imports private code and works unchanged without it.

## Rules that keep the boundary intact

1. **Nothing private is committed here, ever.** This repository's history is public and
   mirrored (PyPI, Zenodo, forks). A later removal does not recall what was published.
2. **Everything already released stays MIT.** Versions 0.1.0 to 0.3.0 are on PyPI and Zenodo
   under the MIT licence and cannot be relicensed retroactively.
3. **Private code reads the public schema only.** If it needs a field that does not exist,
   propose it through the normal Discussion process; do not fork the schema.
4. **No private data in fixtures, tests, issues or the website.**

## Open items before relying on this

- **Contributor terms.** Outside contributions are accepted under the repository's MIT licence,
  and there is no contributor licence agreement. That is fine for keeping *this* repository
  open, but it would complicate relicensing it later. If dual licensing is ever a goal, add a
  CLA or DCO policy *before* accepting substantial outside code.
- **Who owns the private work.** Employer or institutional IP terms apply to anything written
  while affiliated; check them before the private repository is started.
- **Legal review.** This page is an engineering boundary, not legal advice. Have counsel confirm
  the licence and ownership position before any IP release.
