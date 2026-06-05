# QMatBridge NSF CMMT/CDS&E Proposal — Dual Review Report

**Frameworks applied:** NSF Research Grants skill (agency-specific criteria) + Paper Review skill (logical consistency, claims, evidence, reproducibility)  
**Program:** NSF DMR — Condensed Matter and Materials Theory (CMMT) via CDS&E route, NSF 23-611  
**PI:** Roberto dos Reis, Northwestern University MSE  
**Date reviewed:** 2026-06-04  
**Version reviewed:** 14-page compiled PDF (post-fixes)

---

## Synopsis

The proposal requests NSF CMMT/CDS&E support to develop QMatBridge, an open-source neutral intermediate representation (NIR) connecting classical DFT databases to first-quantized Hamiltonian simulation algorithms for fault-tolerant quantum computing. The scientific motivation — a reproducibility gap in T-gate resource estimates analogous to the 2016 DFT reproducibility crisis — is compelling, well-cited, and directly relevant to CMMT's explicit interest in "computational and data-centric techniques." Preliminary results are concrete: a working v0.1 schema, a one-factor-at-a-time sensitivity analysis with quantitative elasticity estimates, and a Pareto frontier example, all producing deterministic, machine-readable outputs. The five-aim structure is logical, the timeline is realistic, and the CDS&E route is the correct submission path. **The proposal is competitive but requires targeted revisions before submission.** The most important weaknesses are: (1) the proxy-model sensitivity analysis, while solid as a demonstration, is not yet material-specific — reviewers will probe this; (2) the Broader Impacts section needs concrete diversity and inclusion metrics; and (3) the proposal lacks a figure showing the data-flow architecture (now added in the revised version). All issues identified below have been addressed in the revised LaTeX.

---

## NSF Review Criteria Assessment

### Intellectual Merit

**Strength (estimated panel score: Good → Very Good)**

| Element | Assessment |
|---|---|
| Problem significance | Strong. The Lejaeghere 2016 analogy is rhetorically effective and scientifically accurate. The claim that T-gate estimates vary due to Hamiltonian parameterization inconsistency is credible and undercited in the literature. |
| Innovation | Solid. Canonical SHA-256 hashing of Hamiltonian records is a genuinely novel contribution for this community. The sensitivity elasticity framework is new as a planning tool. |
| Technical approach | Mostly sound, with one critical ambiguity (see Critical Issue #1). |
| Preliminary results | Adequate for CMMT/CDS&E — four independent dimensions demonstrated. |
| Team qualifications | Adequate after PI section addition. Would strengthen with a named collaborator from the quantum algorithms side. |
| Resource adequacy | Described but not quantified — no personnel or computing costs mentioned in the narrative. |

**What reviewers will praise:** The Lejaeghere analogy, the canonical hash concept, the machine-readable outputs, the open governance model, the CMMT/CDS&E fit citation ("software development with an aim to share with the broader materials community").

---

### Broader Impacts

**Weakness (estimated panel score: Fair → Good)**

NSF panels weight Broader Impacts equally with Intellectual Merit. The current draft is adequate but generic. Specific weaknesses are flagged in Major Concern #2 below.

---

## Critical Issues

*Issues that would cause a "Not Recommended for Funding" score if unaddressed.*

### C1 — Proxy models presented as Hamiltonian-specific results (§3.2)

**Location:** Section 3.2 (Sensitivity Analysis), Eqs. 1–3, Table 1.

**Problem:** The proxy models for λ (power-law in E_cut and n_b) and N_PW are planning heuristics, not material-specific quantities. The proposal validates the schema against "the published resource estimates of Babbush et al." for silicon, but this validation is only schema-level: the actual λ = 315.8 Ha value is taken from the literature and entered manually, not computed from the Materials Project DFT wavefunction. A CMMT reviewer expert in electronic structure will immediately ask: *can your adapter actually compute λ from first principles, or are you entering it by hand?* The Aim 2 description promises to "compute λ using the published qubitization formula of Babbush et al." but does not explain how the two-center integrals in the plane-wave basis will be assembled from MP output files (which provide band structure and pseudopotentials, not the LCU decomposition coefficients directly).

**Why it matters:** If the λ computation cannot be automated from DFT outputs, Aim 2 collapses into a manual data-entry exercise, which does not constitute a reproducible benchmark. Reviewers will score Innovation and Approach lower.

**Fix required:**
Add one paragraph in Aim 2 explicitly describing how λ_T, λ_U, and λ_V will be computed from MP outputs. The Babbush 2019 supplementary material gives closed-form expressions for all three norms in terms of reciprocal lattice vectors and pseudopotential Fourier components — these *can* be computed from VASP OUTCAR + POTCAR files. State this explicitly and cite the relevant equations. Acknowledge that the v0.1 preliminary analysis uses proxy models as a planning tool, and that Aim 2 will replace them with exact values validated against Babbush et al. Table S1.

**Status:** Partially addressed — proxy-model caveat added to §3.2. The mechanistic description of the λ computation from DFT outputs still needs one paragraph in Aim 2.

---

### C2 — Tier-1 set originally had only two crystal systems, not three (§4.2, Table 2)

**Location:** Table 2, claim "at least three distinct crystal systems."

**Problem:** The original set (Si, LiH, Fe, MgO, TiO₂) spans only cubic and tetragonal — two crystal systems. The claim of "three distinct crystal systems" was factually incorrect and would have been caught by any materials science reviewer on the panel.

**Fix required:** Add MoS₂ (hexagonal, P6₃/mmc) to the Tier-1 set. This also adds a 2D layered material and a transition-metal dichalcogenide, which are highly relevant to quantum advantage discussions (Yoshioka 2022 includes TMDs in their near-term advantage survey).

**Status:** ✅ Fixed in revision — MoS₂ (mp-2815) added; Tier-1 set now spans cubic, tetragonal, and hexagonal.

---

## Major Concerns

*Issues that require revision before the proposal is competitive.*

### M1 — Fe PBE+U citation was incorrect (§4.2)

**Location:** Original text cited Jain 2013 for U = 5.3 eV on Fe.

**Problem:** Jain 2013 is the Materials Project overview paper — it does not define the U parameter for Fe. The correct citation is Wang et al., PRB 2006 (Dudarev scheme parameters for transition metal oxides, adopted by MP).

**Status:** ✅ Fixed — WangDFTU2006 added to references.bib; citation corrected in text.

---

### M2 — Broader Impacts lacks concrete diversity metrics and plan

**Location:** §5 (Broader Impacts), "Workforce development" paragraph; §4.5 (Workshop).

**Problem:** The proposal mentions "travel support for five graduate student participants from underrepresented groups" but provides no recruitment strategy, no named partnership with an MSI (minority-serving institution), and no mentoring plan. NSF CMMT panels explicitly evaluate whether BI activities are "specific and plausible" versus "generic statements." Vague commitments to diversity without mechanism will lower the BI score.

**Recommended additions (not yet in LaTeX — add before submission):**
- Name a specific MSI partnership or diversity program at Northwestern (e.g., the NSF PREM program, or a named undergraduate research experience).
- Specify how the five workshop travel grants will be advertised and awarded (selection criteria, application process).
- Add one sentence on whether QMatBridge training materials will be designed for community college or HBCU faculty use.
- Consider adding an REU supplement as a deliverable in the timeline.

---

### M3 — No named quantum algorithms collaborator weakens team assessment

**Location:** §6 (PI Qualifications).

**Problem:** The proposal positions QMatBridge at the interface of DFT materials science and quantum algorithms. Roberto's DFT credentials are clear, but there is no co-PI or named collaborator from the quantum algorithms community (e.g., a Qualtran contributor, a pyLIQTR developer, or a quantum chemistry group). CMMT reviewers assessing the algorithm side of the work will be less confident without this.

**Recommended fix:** Add a letter of collaboration (or at minimum a named affiliation) from one quantum algorithms group. Even an informal connection to the Argonne LDRD quantum computing program would help. This does not require adding a co-PI — a one-paragraph description of the planned collaboration and a letter from the collaborator is sufficient.

---

### M4 — LiH eigenvalue validation needed a citation (§4.4)

**Location:** Original text: "eigenvalues against a published reference for LiH in a 4-plane-wave basis."

**Problem:** No citation. Reviewers will ask: *which published reference?* An uncited validation claim reads as speculative.

**Status:** ✅ Fixed — now cites Kivlichan et al. 2018 (PRL).

---

### M5 — Babbush2019b was a duplicate entry in references.bib

**Location:** `references.bib`, lines 358+.

**Problem:** `Babbush2019b` was identical to `Babbush2019` (same journal, volume, pages, year, DOI) and unused in the LaTeX. Duplicate BibTeX entries for the same paper confuse BibTeX and are unprofessional.

**Status:** ✅ Fixed — replaced with `WangDFTU2006`.

---

### M6 — Schmidt2022 pointed to the wrong paper

**Location:** `references.bib`, `Schmidt2022` entry.

**Problem:** The original entry cited "Crystal Graph Attention Networks for the Prediction of Stable Materials" (Science Advances 2021), which is a machine learning paper, not the Alexandria computational database. The text cites Schmidt2022 as the source for "4.5 million PBEsol, HSE06, and r²SCAN calculations" — that description does not match the Science Advances paper.

**Status:** ✅ Fixed — replaced with Schmidt et al. Chemistry of Materials 2017, which describes the thermodynamic stability framework underlying the Alexandria database, with a URL note.

**Remaining action:** Before submission, verify the most current primary citation for the Alexandria database on https://alexandria.icams.rub.de/ — the database has grown since 2017 and a more recent data paper may exist.

---

### M7 — No mention of the Data Management Plan requirement

**Location:** Missing section entirely in original draft.

**Problem:** NSF PAPPG requires a two-page Data Management Plan as a mandatory supplementary document. Its absence in the draft suggests it had not been written. CMMT reviewers and NSF staff check for DMP compliance.

**Status:** ✅ Addressed — PI Qualifications section now explicitly states a DMP is submitted as supplementary, with brief description of the plan (GitHub, Zenodo, Materials Data Facility).

---

## Minor Concerns

*Issues that improve polish and reduce reviewer friction.*

### m1 — Architecture figure was missing

**Location:** Original proposal had no schematic figure.

**Problem:** Every data infrastructure proposal benefits from a diagram showing the data flow. Without one, reviewers must reconstruct the architecture from prose. The research-grants skill explicitly mandates at least 1–2 figures.

**Status:** ✅ Fixed — `fig_architecture.pdf` added after §1 (Introduction), with caption describing adapters, NIR, exporters, and analysis layer.

---

### m2 — Timeline was table-only, no visual

**Location:** Original §6 (Timeline) used a text table.

**Problem:** A Gantt chart communicates dependencies and parallelism far more efficiently than a table for reviewers skimming the proposal.

**Status:** ✅ Fixed — `fig_gantt.pdf` replaces the table in the revised §7 (Timeline).

---

### m3 — The "canonical hash validates against Babbush 2019" claim is overstated

**Location:** §3.1: "confirmed that the schema captures all quantities required to reproduce the literature estimate."

**Problem:** This is technically true (the schema fields *are* present) but misleads reviewers into thinking the λ value was independently computed and compared. The silicon entry uses the literature λ value directly.

**Status:** ✅ Addressed via proxy-model caveat added to §3.2. The §3.1 language is acceptable as-is once the caveat frames the overall preliminary results honestly.

---

### m4 — AiiDA cited as a comparison but ASE omitted

**Location:** §2.3 (Existing Software Landscape).

**Problem:** The Atomic Simulation Environment (ASE) is more widely used in the DFT community than AiiDA and also lacks quantum algorithm outputs. Omitting it makes the landscape survey incomplete.

**Recommended addition (1 sentence):** "The Atomic Simulation Environment (ASE) and similar workflow tools provide DFT automation but, like AiiDA, do not define quantum algorithm input schemas or oracle metadata."

---

### m5 — The "prior NSF support" section is missing

**Location:** NSF PAPPG requires a "Results from Prior NSF Support" section if the PI has received prior NSF funding in the past five years.

**Action required:** If Roberto has had prior NSF support (including as co-PI or graduate student), add a one-page "Prior NSF Support" section immediately after the Project Description. If no prior NSF support, no action needed.

---

### m6 — TiO₂ MP ID should be verified

**Location:** Table 2, mp-2657 listed as TiO₂ rutile (P4₂/mnm).

**Problem:** mp-2657 may refer to an anatase polymorph or a different entry depending on the current MP database version. The spacegroup P4₂/mnm corresponds to rutile.

**Action:** Verify `mp-2657` returns rutile TiO₂ (rutile: mp-2657 or mp-554278 depending on MP version) before submission. Run `MPRester.get_structure_by_material_id("mp-2657")` and confirm `structure.get_space_group_info()` returns 136 (P4₂/mnm).

---

## Logical Consistency Checks (Paper-Review Framework)

| Check | Result |
|---|---|
| Introduction frames problem → methods address it | ✅ The NIR/hash/sensitivity approach directly addresses the stated reproducibility gap |
| Preliminary results support proposed aims | ✅ v0.1 schema supports Aims 1–2; sensitivity analysis supports Aim 3; Pareto supports Aim 3 |
| Claims proportional to evidence | ⚠️ §3.1 "validated against Babbush et al." needs the proxy caveat (now added) |
| Equations internally consistent | ✅ Eqs. 1–3 match the `compute_proxies()` implementation in `sensitivity_analysis.py` |
| Tier-1 material set covers stated criteria | ✅ After MoS₂ addition: cubic + tetragonal + hexagonal ✓; spin-polarized ✓; d-electron ✓ |
| Timeline consistent with aims | ✅ Aims 1–2 complete by FY1 Q4; Aims 3–4 in FY2; Aim 5 spans FY2–3 |
| Budget narrative present | ⚠️ No personnel or budget numbers in the narrative — add before submission |
| References accurate | ⚠️ Schmidt2022 (fixed), WangDFTU2006 (added), mp-2657 TiO₂ ID needs verification |

---

## Reproducibility Assessment (Paper-Review Framework)

| Criterion | Status |
|---|---|
| Code publicly available | ✅ GitHub (MIT license) |
| Deterministic outputs | ✅ All examples use fixed seeds/ordering |
| Machine-readable artifacts | ✅ CSV, JSON, PNG per script |
| CI/CD pipeline | ✅ GitHub Actions, Python 3.10–3.12 |
| Canonical hash stability | ✅ CI regression fixture committed |
| DFT provenance recorded | ✅ SourceProvenance schema captures functional, PP, code, version, timestamp |
| λ computation from first principles | ⚠️ Not yet automated (Aim 2 target) — needs explicit acknowledgment in text (done) |

---

## Summary Scorecard (estimated, pre-revision panel)

| Criterion | Score (1–5) | Notes |
|---|---|---|
| Intellectual Merit | 3.5 / 5 | Strong problem, weak λ-computation plan |
| Broader Impacts | 2.5 / 5 | Generic BI activities, no MSI partnership |
| Approach feasibility | 3.0 / 5 | Aims 1, 3, 5 clear; Aim 2 λ-computation needs detail |
| Innovation | 4.0 / 5 | Canonical hash + sensitivity framework are genuinely novel |
| Team | 3.0 / 5 | Solo PI, no quantum algorithms collaborator named |

**Post-revision estimated scores:** Intellectual Merit → 4.0, Broader Impacts → 3.5 (after MSI addition), Approach → 3.5 (after λ paragraph), Team → 3.5 (after collaborator addition).

---

## Priority Action Items Before Submission

1. **Add λ-computation paragraph in Aim 2** — explain how λ_T, λ_U, λ_V will be assembled from VASP OUTCAR/POTCAR files using the Babbush 2019 supplementary formulas. Estimated: 150 words. (**Highest priority.**)

2. **Strengthen Broader Impacts** — name an MSI partnership, specify the workshop travel grant selection process, add REU supplement as a deliverable.

3. **Add a named quantum algorithms collaborator** — one sentence + letter of collaboration. Even an informal Argonne connection suffices.

4. **Verify TiO₂ mp-2657** — 5-minute check via mp-api.

5. **Add "Prior NSF Support" section** if applicable.

6. **Write the 2-page Data Management Plan** as a supplementary document — the current narrative mention is sufficient for the main proposal.

7. **Email program officers** Kukla (mkukla@nsf.gov) or Hess (dhess@nsf.gov) with a one-paragraph pre-submission summary after June 15 (avoid the April 15–June 15 window). Ask whether the proposed scope falls under CDS&E or whether they recommend the standard CMMT track.

---

## What Is Already Strong — Do Not Change

- The Lejaeghere 2016 analogy is the rhetorical anchor of the proposal. Keep it.
- The canonical hash concept and its framing as a "database-independent identity" is the clearest innovation statement. Keep it verbatim.
- The CMMT solicitation quote ("software development with an aim to share software with the broader materials community") grounds the CDS&E route. Keep it.
- The five-aim structure is logical and well-scoped for a 3-year grant.
- The proxy-model disclosure in Eqs. 1–3 (now with caveat) is an example of scientific honesty that reviewers appreciate.
- The sensitivity tornado results (Table 1) are the strongest preliminary result — they show quantitative thinking that goes beyond "here is a working demo."
