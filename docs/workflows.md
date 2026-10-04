# How the workflows work

Four automated pieces keep the project healthy. Three run on GitHub; one is a manual data
step on a maintainer's machine, on purpose.

| Workflow | File | Runs when | What it does |
| --- | --- | --- | --- |
| **CI** | `.github/workflows/python-package.yml` | every pull request to `main`, every push to `main` | ruff and mypy; tests on Python 3.10, 3.11, 3.12 with an 85 % coverage floor; strict docs build; package build and `twine check` |
| **Deploy site** | `.github/workflows/pages.yml` | every push to `main`, or manually | builds the docs and the landing page, publishes both to GitHub Pages |
| **Live integration tests** | `.github/workflows/integration.yml` | nightly, or manually; never on pull requests | runs the `integration`-marked tests against the live Materials Project API |
| **Data run** | `python -m benchmarks.build_tier1_fixtures` | by hand | fetches live data, checks it against the Tier-1 spec, writes fixtures and the website data |

## The normal flow

```text
branch  ->  pull request  ->  CI (must pass)  ->  merge to main  ->  Deploy site
```

Pull-request tests never call external APIs or use secrets, so CI is fast and safe for forks.

## Live integration tests

Unit tests use a fake Materials Project client. The integration tests check the real thing:

1. **Spec test** – each Tier-1 material, fetched live, still satisfies `benchmarks/tier1.py`
   (species, electron count, spin, functional).
2. **Drift test** – the live record still produces the *same* `canonical_hash()` and plane-wave
   count as the committed fixture in `benchmarks/fixtures/`.

If either fails, the workflow opens an issue labelled `integration-failure` (or comments on the
open one) and closes it when the tests pass again. A failure means one of two things:

- the adapter broke: fix the code; or
- Materials Project now serves different data: regenerate the fixtures (below), review the diff,
  and commit it.

**One-time setup.** Add the API key as a repository secret named `MP_API_KEY` (Settings →
Secrets and variables → Actions, or `gh secret set MP_API_KEY`). Until it exists the workflow
passes and logs that it skipped, so it is safe to merge first. Use a key you are willing to
store in GitHub, and rotate it if it has been shared anywhere.

Run the same tests locally with your key in the gitignored `.env`:

```bash
pytest -m integration -o addopts="--tb=short"
```

## Regenerating fixtures and website data

```bash
cp .env.example .env          # then put your key in .env (never in .env.example)
python -m benchmarks.build_tier1_fixtures --site website/data/examples.json
```

Each material is checked against its spec before anything is written; a mismatch prints a
`[FAIL]` line and writes nothing for that material. Commit the changed
`benchmarks/fixtures/*.json` and `website/data/examples.json` in a pull request. The site updates
when it merges. This step stays manual so the key stays on your machine and the published site
never calls the Materials Project.

## Deploying

`pages.yml` builds MkDocs into `_site/docs/`, builds the landing page from
`website/index.template.html` plus `website/data/examples.json` (`tools/build_site.py`), and
publishes `_site/`. The company page lives in a separate repository, `q-matsuite.github.io`,
which is what serves `q-matsuite.com` and places this site under `/qmatbridge/`.

Pages must be set to **GitHub Actions** as its source in this repository's settings.
