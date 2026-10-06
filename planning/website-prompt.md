# QMatBridge website — build spec

Status: **approved; implemented** in `website/index.template.html` (built by `tools/build_site.py`).

## Goal

A single-page landing site that tells a fault-tolerant-quantum-algorithms researcher,
in under a minute, what QMatBridge is, why provenance matters, and how to try it. It
is a research-software page, not a SaaS pitch.

## Hosting and URLs

- GitHub Pages, project site: `https://q-matsuite.com/qmatbridge/`.
- Landing page at the site root; MkDocs output under `/docs/` (see `mkdocs.yml`).
- Source in `website/` (`index.template.html`, `favicon.svg`, `data/examples.json`); `tools/build_site.py` embeds the data and writes `index.html` (gitignored; built in CI). The repo's
  `.gitignore` already ignores `site/`, so do not use that name.
- **All asset and link URLs must be relative** (no leading `/`), so the same build
  works at `/qmatbridge/` today and at a custom domain root later. Moving to a custom
  domain later = add `website/CNAME`; nothing else changes.
- Deployed by a GitHub Actions workflow (build MkDocs → copy `website/` → deploy
  Pages artifact). No other build tooling for the landing page.

## Content rules (honesty)

- Describe the project as **early-stage**. Schema + JSON I/O + MP adapter exist;
  exporters are planned.
- PyPI has 0.2.0 (`pip install qmatbridge`); the `[mp]` extra needs Python 3.11+. Do not claim user counts, testimonials,
  benchmark results, partner logos, or funding. No fabricated metrics.
- Install snippet is `pip install qmatbridge` (and `"qmatbridge[mp]"`).
- Citation block matches `README.md` and `CITATION.cff` exactly.

## Examples explorer (added on review)

Right after the hero: a material picker (Si, GaN, LiCoO₂ — semiconductor, wide-gap
III–V, battery cathode) driving a rotatable unit-cell viewer (drag or arrow keys, bonds
inferred from covalent radii), stat tiles (formula, space group, electrons, plane
waves, functional, spin, MP source, hash) and Python / JSON tabs with copy buttons.
All values come from `website/data/examples.json`, which is generated from live
Materials Project data by `benchmarks/build_tier1_fixtures.py --site ...` after the
entries pass the Tier-1 spec checks. With no data file the section is hidden.

## Design pass 2 (stunning pass)

- **Hero:** slowly rotating diamond-cubic lattice drawn on a canvas (decorative,
  `aria-hidden`, pauses off-screen and when the tab is hidden, static under
  `prefers-reduced-motion`); animated data flow along the pipeline arrows.
- **Examples explorer:** per-material fingerprint image generated from the hash, six stat
  tiles, a scale comparison (plane waves, electrons) across the three materials.
- **Fingerprint demo (`#fingerprint`):** edit functional, cutoff, electrons, spin and tags;
  the page recomputes the SHA-256 in the browser with the same rules as
  `QMatEntry.canonical_hash()` (pure-JS SHA-256, so it works outside secure contexts) and
  highlights the changed characters and fields. A self-check compares the recomputed
  hash of the fetched values with the library's value and says so if they differ.
- **Polish:** scroll reveal, scroll-progress bar, active-section nav, section numbering.
  All motion is disabled under `prefers-reduced-motion`.

## Credit

Footer credits **Roberto dos Reis (@rmsreis)** as creator and maintainer, links to
github.com/rmsreis, and `<meta name="author">` carries the same.

## Sections (single `index.html`, hash navigation)

1. **Hero** — name, one-line tagline ("Materials databases to first-quantized
   Hamiltonians, with provenance."), two actions: *Get started* (→ `#install`) and
   *Docs* (→ `docs/`). Below: pipeline SVG
   `Materials Project · OQMD · OPTIMADE → QMatEntry (NIR) → OpenFermion · qualtran · pyLIQTR`.
2. **The problem** — two short paragraphs: one-off scripts, no shared provenance, two
   groups reporting T-counts for "silicon" can't verify they used the same Hamiltonian.
3. **What a `QMatEntry` records** — provenance, structure, basis, oracle cost, exports;
   plus `canonical_hash()`.
4. **Schema** — table of the core dataclasses and their roles.
5. **Example** — see *Examples explorer* above (placed directly after the hero).
6. **Install** — from-source commands with copy buttons; optional extras.
7. **Who it is for** — algorithm researchers, RSEs, resource-estimation groups; and
   who it is *not* for (use pymatgen/ASE for general materials informatics).
8. **Roadmap** — v0.1 → v0.5 as a compact timeline; done vs. planned clearly marked.
9. **Community** — Discussions, Issues, CONTRIBUTING, GOVERNANCE, code of conduct.
10. **Cite** — BibTeX block with copy button; footer with license (MIT) and repo link.

## Design

- Dark mode only. Slate background, one accent colour, text contrast ≥ 4.5:1.
- Colours as CSS custom properties on `:root` (oklch). Proposed starting tokens —
  adjust on review:
  `--bg: oklch(0.18 0.01 255)`, `--surface: oklch(0.22 0.012 255)`,
  `--text: oklch(0.93 0.01 255)`, `--muted: oklch(0.72 0.015 255)`,
  `--accent: oklch(0.78 0.12 200)`, `--border: oklch(0.32 0.015 255)`.
- Type: DM Serif Display (headings), Inter (body), JetBrains Mono (code), via Google
  Fonts with `font-display: swap` and system fallbacks.
- Avoid: gradient buttons, three-column icon grids, glow/blur blobs, stock imagery,
  emoji as iconography.
- Logo: inline SVG mark (a "Q" whose tail is a bridge span) using `currentColor`;
  must read at 32 px (favicon) and at full size.

## Technical requirements

- One HTML file, inline CSS and a small inline script (copy-to-clipboard,
  `aria-live` confirmation). No framework, no bundler, no trackers or analytics.
- Semantic landmarks (`header/nav/main/section/footer`), skip link, visible focus
  rings, full keyboard operation, `prefers-reduced-motion` respected.
- `<title>`, meta description, canonical URL, Open Graph/Twitter tags, `favicon.svg`.
- Responsive from 360 px up; no horizontal page scroll.

## Acceptance criteria

Verified in the browser pane before the PR is marked ready:

1. **Pipeline diagram** reads cleanly at 375 px — stacks vertically on narrow screens.
2. **Code blocks** render in JetBrains Mono; each copy button copies exact text and
   announces success; works without the font loading (fallback stack).
3. **Schema table** at 375 px has no horizontal page overflow (wraps, or scrolls
   inside its own container).
4. Lighthouse: Accessibility ≥ 95, Best Practices ≥ 95, SEO ≥ 95, no console errors.
5. All internal links resolve under `/qmatbridge/` and with the Pages path removed.
6. Every factual claim on the page is traceable to the README, docs, or code.
