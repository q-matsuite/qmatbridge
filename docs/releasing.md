# Releasing

A release is a version bump, a tag, and one automated workflow. PyPI is published with
**trusted publishing**: GitHub proves its identity to PyPI, so no API token is stored anywhere.

## Where things stand

- `qmatbridge` **0.1.0** is already on PyPI (published 2026-06-04, with the old repository
  URLs). Versions cannot be re-uploaded, so the next release must be higher than 0.1.0.
- The next version will update PyPI's project links to this repository.
- TestPyPI has no `qmatbridge` project yet, so the dry run needs a *pending* publisher.

## One-time setup

1. **PyPI trusted publisher.** On pypi.org open the `qmatbridge` project → *Manage* → *Publishing*
   → add a GitHub publisher with: owner `q-matsuite`, repository `qmatbridge`, workflow
   `release.yml`, environment `pypi`.
2. **TestPyPI (optional dry run).** On test.pypi.org → *Account* → *Publishing*, add a pending
   publisher for project `qmatbridge` with the same owner, repository and workflow, environment
   `testpypi`.
3. **GitHub environments.** In the repository: *Settings → Environments*, create `pypi` and
   `testpypi`. For `pypi`, add yourself as a **required reviewer**, so no tag can publish to
   PyPI without your explicit approval.
4. **Zenodo DOI (optional).** Sign in at zenodo.org with GitHub, open *GitHub* settings, grant
   access to the `q-matsuite` organisation if asked, and switch `q-matsuite/qmatbridge` on.
   Every GitHub release is then archived and gets a DOI.

## Cutting a release

1. Make sure `main` is green, including the nightly live tests (see [workflows](workflows.md)).
2. In one pull request:
   - set `version` in `pyproject.toml`;
   - rename `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] — date`, add a fresh empty
     `## [Unreleased]` above it, and update the compare links at the bottom;
   - update `version` and `date-released` in `CITATION.cff` and the version in the README BibTeX.
3. *Optional dry run:* Actions → **Release** → *Run workflow*. This builds, checks and publishes
   to TestPyPI only.
4. After the pull request merges, tag the merge commit and push the tag:

   ```bash
   git checkout main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

5. The workflow then: verifies the tag equals the `pyproject.toml` version, builds the sdist and
   wheel, runs `twine check`, installs the wheel in a clean environment as a smoke test,
   waits for your approval of the `pypi` environment, publishes to PyPI, and creates a GitHub
   release whose notes are the matching `CHANGELOG.md` section.
6. Verify in a fresh virtual environment:

   ```bash
   pip install --no-cache-dir "qmatbridge==X.Y.Z"
   python -c "import qmatbridge; print(qmatbridge.__version__)"
   ```

7. If Zenodo is on, add the DOI badge to the README and a `doi:` line to `CITATION.cff`.

## If something goes wrong

- **Tag does not match the version:** the first job fails before anything is published. Fix the
  version, delete the tag (`git push --delete origin vX.Y.Z`), and retag.
- **Published a bad version:** PyPI cannot overwrite files. *Yank* the release on pypi.org and
  publish a higher version.
- **Trusted publishing is rejected:** the publisher's owner, repository, workflow file name and
  environment must match exactly what is configured on PyPI.
