# Support

This document explains where to get help, report problems, and engage with the
QMatBridge community.

---

## Before You Ask

Please check the following resources first:

- **[README.md](README.md)** — quickstart, installation, and project overview
- **[docs/vision.md](docs/vision.md)** — design rationale and scope
- **[examples/](examples/)** — working code examples
- **[GitHub Discussions](https://github.com/QMatBridge/qmatbridge/discussions)** —
  prior questions and community answers
- **[GitHub Issues](https://github.com/QMatBridge/qmatbridge/issues)** — known
  bugs and feature requests

---

## Choosing the Right Channel

| Situation | Where to go |
| --- | --- |
| "How do I…?" usage question | [GitHub Discussions → Q&A](https://github.com/QMatBridge/qmatbridge/discussions/categories/q-a) |
| Unexpected behavior, possible bug | [GitHub Issues → Bug Report](https://github.com/QMatBridge/qmatbridge/issues/new?template=bug_report.yml) |
| Feature idea or adapter proposal | [GitHub Issues → Feature Request](https://github.com/QMatBridge/qmatbridge/issues/new?template=feature_request.yml) |
| Schema or architecture discussion | [GitHub Discussions → Ideas](https://github.com/QMatBridge/qmatbridge/discussions/categories/ideas) |
| Security vulnerability | **Email only** — see [SECURITY.md](SECURITY.md) |
| Code of Conduct concern | **Email only** — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) |

**Please do not** use GitHub Issues for general usage questions — Discussions
keep Q&A searchable and separate from the bug tracker.

---

## Reporting a Bug

Use the [bug report template](https://github.com/QMatBridge/qmatbridge/issues/new?template=bug_report.yml)
and include:

- QMatBridge version (`python -c "import qmatbridge; print(qmatbridge.__version__)"`)
- Python version and OS
- Minimal reproducible example
- Full traceback if applicable

The more detail you provide, the faster we can help.

---

## Response Time Expectations

QMatBridge is maintained on a best-effort basis by a small team. Typical
response times:

| Channel | Expected response |
| --- | --- |
| GitHub Issues (bugs) | Within 7 business days |
| GitHub Discussions | Within 7 business days |
| Security reports (email) | Within 72 hours |

If your issue is urgent and relates to a reproducible correctness bug in the
core schema, please tag the issue `priority: high` and explain the impact.

---

## Commercial or Institutional Support

There is currently no commercial support offering for QMatBridge. If your
organization is interested in a collaboration, grant co-authorship, or
institutional partnership, please reach out at **robertomsreis@gmail.com**.

---

## Contributing a Fix

If you find a bug and would like to fix it yourself, please read
[CONTRIBUTING.md](CONTRIBUTING.md). Small, well-scoped bug-fix PRs are very
welcome and are the fastest path to resolution.
