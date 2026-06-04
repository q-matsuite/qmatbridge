## Summary

<!-- One paragraph describing what this PR does and why. -->

## Type of change

- [ ] Bug fix
- [ ] New adapter (upstream database)
- [ ] New exporter (downstream framework)
- [ ] Schema change (see CONTRIBUTING.md — requires prior discussion)
- [ ] Documentation
- [ ] CI / infrastructure
- [ ] Other

## Related issues

Closes #<!-- issue number -->

## Changes

<!-- Bullet list of concrete changes: files added/modified, new public API. -->

## Testing

- [ ] New tests added for all new behaviour
- [ ] Existing tests still pass (`pytest`)
- [ ] Integration tests added (if applicable) and marked `@pytest.mark.integration`

## Schema changes (fill in if applicable)

- [ ] This PR modifies `QMatEntry`, `MaterialReference`, or `HamiltonianMetadata`
- [ ] A GitHub Discussion was opened and approved before this PR was opened
- [ ] `CHANGELOG.md` entry added with **[BREAKING]** marker if applicable
- [ ] Migration note added for any field rename or removal

## Checklist

- [ ] `ruff check .` passes with no errors
- [ ] `mypy qmatbridge/` passes with no new errors
- [ ] `pytest` passes (unit tests only; integration tests require env vars)
- [ ] Docstrings updated for any new or changed public symbols
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
