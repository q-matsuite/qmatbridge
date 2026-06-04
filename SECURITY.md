# Security Policy

## Supported Versions

QMatBridge is pre-1.0 software. Security fixes are applied to the **latest
released version** on the `main` branch only.

| Version | Supported |
| --- | --- |
| `0.x` (latest) | Yes |
| Older patch releases | No — please upgrade |

---

## Scope

QMatBridge is a data-layer library with no network-facing components, no
authentication system, and no server processes. The most likely security
concerns are:

- **Deserialization vulnerabilities** in JSON/YAML import paths (planned for v0.1)
- **Dependency vulnerabilities** in optional extras (pymatgen, mp-api, etc.)
- **Credential exposure** via the Materials Project or other database API keys
  when using adapter modules

If you are unsure whether an issue is in scope, please report it privately
and we will evaluate together.

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues by emailing the maintainer directly:

**Roberto Reis — robertomsreis@gmail.com**

Include in your report:

1. A description of the vulnerability and its potential impact
2. Steps to reproduce or a minimal proof-of-concept (if safe to share)
3. The version(s) of QMatBridge affected
4. Any suggested mitigations you have identified

You will receive an acknowledgement within **72 hours** and a substantive
response within **7 days**.

---

## Disclosure Policy

We follow a **coordinated disclosure** model:

1. Reporter contacts maintainers privately.
2. Maintainers confirm the issue and assess severity within 7 days.
3. A fix is developed on a private branch and a target release date is set
   (typically within 30 days for high-severity issues, 90 days otherwise).
4. A patched release is published.
5. A public advisory is posted in the GitHub Security Advisories tab, crediting
   the reporter (unless they prefer to remain anonymous).

We ask reporters to refrain from public disclosure until the patch is released
or until 90 days have elapsed since the initial report, whichever comes first.

---

## Dependency Security

QMatBridge uses [Dependabot](https://docs.github.com/en/code-security/dependabot)
for automated dependency vulnerability alerts. Maintainers review and apply
security updates promptly.

If you discover a vulnerability in one of our dependencies, please also report
it upstream to that project.

---

## API Key Guidance

When using database adapters (e.g., the Materials Project adapter), API keys
are passed by the caller and are never stored, logged, or serialized by
QMatBridge. As a best practice:

- Store API keys in environment variables, not in source files
- Never commit `.env` files or `api_keys.json` to the repository
  (both are listed in `.gitignore`)
- Rotate keys immediately if accidental exposure is suspected
