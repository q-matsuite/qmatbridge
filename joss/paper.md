---
title: 'QMatBridge: a provenance-tracked bridge from materials databases to quantum-simulation Hamiltonians'
tags:
  - Python
  - quantum computing
  - quantum simulation
  - materials science
  - Hamiltonian simulation
  - reproducibility
authors:
  - name: Roberto dos Reis
    affiliation: 1
affiliations:
  - name: Department of Materials Science and Engineering, Northwestern University, Evanston, IL 60208, USA
    index: 1
date: 10 October 2026
bibliography: paper.bib
---

<!--
DRAFT, not submitted. Before submitting to JOSS the author must: confirm every claim below
against the released version, add an ORCID if wanted, check the current JOSS requirements
(paper format, AI-usage disclosure, minimum public history), and replace the research-impact
placeholders with real uses. Build locally with the openjournals/inara Docker image.
-->

# Summary

QMatBridge is a Python package that turns records from classical materials databases into a
neutral, serializable description of a plane-wave Hamiltonian and its quantum-simulation
oracle, and hands that description to downstream tools. A `QMatEntry` records where a
material came from (database, identifier, functional, pseudopotential, code), its crystal
structure with atomic positions and valence charges, the plane-wave basis, and, if known, the
LCU 1-norm and oracle parameters used for fault-tolerant resource estimates. A canonical
SHA-256 hash over the physically meaningful fields lets two groups check that they used the
same Hamiltonian. Adapters read the Materials Project, OQMD, and any OPTIMADE-compliant
database; exporters write NumPy arrays, an OpenFermion `InteractionOperator`, and a Pauli
linear combination of unitaries for Qualtran, pyLIQTR, and Cirq. A deduplication module groups
entries that describe one material across databases. The core has no runtime dependencies.

# Statement of need

Groups developing fault-tolerant Hamiltonian-simulation algorithms (block encodings,
qubitization, first-quantized plane-wave methods) need realistic Hamiltonians to benchmark
them [@babbush2019sublinear; @su2021firstq]. The usual route is a one-off script that pulls
DFT data from a database, reformats it, and feeds it to a compiler. Such scripts are rarely
shared, rarely work with more than one framework, and omit the provenance needed to compare
results: when two papers report gate counts for "silicon", nothing says they used the same
cell, cutoff, or functional. QMatBridge fixes the representation, records the provenance, and
makes the identity of a calculation checkable, so that a benchmark can be stated as a set of
entry hashes.

# State of the field

Several tools cover neighbouring ground, and QMatBridge is built to connect to them rather
than replace them.

*Hamiltonian benchmark sets.* HamLib [@sawaya2024hamlib] is a curated, peer-reviewed library
of qubit Hamiltonians for benchmarking algorithms and hardware, with instances from 2 to 1000
qubits across molecular electronic structure, Fermi-Hubbard, Heisenberg and other models and
combinatorial problems. It is a dataset of finished Hamiltonians and is far larger and better
validated than anything QMatBridge ships. QMatBridge addresses a different step: it keeps the
representation *before* a qubit mapping, records which database record and which calculation a
Hamiltonian came from, and generates entries on demand from materials databases. It does not
duplicate HamLib's instance families, and a HamLib-format writer would be a natural exporter.

*Fermionic Hamiltonian toolkits.* OpenFermion [@mcclean2020openfermion] represents and
transforms fermionic Hamiltonians and has its own plane-wave generator for a given grid.
QMatBridge uses it as an export target, and the test suite checks the exported tensors against
OpenFermion's `plane_wave_hamiltonian`.

*Structure libraries and database standards.* pymatgen [@ong2013pymatgen] and ASE
[@larsen2017ase] handle crystal structures, the Materials Project API [@ong2015mpapi] and
OQMD [@saal2013oqmd] serve calculations, and OPTIMADE [@andersen2021optimade] standardizes
queries. None of them describes a Hamiltonian or its simulation oracle; QMatBridge consumes
them and adds that layer, with provenance in the spirit of the FAIR principles
[@wilkinson2016fair].

*Resource estimation.* Qualtran and pyLIQTR implement algorithms and cost them. QMatBridge
supplies the inputs they need (the LCU decomposition, state-register sizes) and the record of
where those inputs came from.

To our knowledge no existing package maps materials-database records to a Hamiltonian
description with recorded provenance and a verifiable identity; this claim should be
re-checked at submission.

# Software design

Adapters and exporters are plugins discovered through Python entry points, so third-party
packages add sources and targets without changing the core. The hash covers eleven
identity fields and, when positions are recorded, the geometry as fixed six-decimal strings
so that the same value is produced in Python and in the project's web page. The exported
Hamiltonians are a deliberately simple *model* (point ions at the valence charge, Gamma
point, Ewald constant) and are not the DFT Hamiltonian of the source calculation; this is
stated in the documentation and recorded in each export. Version 0.6 is tested on
Python 3.10 to 3.14 with continuous integration, a live-API workflow, and recorded-response
tests for the adapters.

# Research impact statement

<!-- AUTHOR TO COMPLETE with real evidence: papers or benchmarks that use QMatBridge entries,
collaborators, users, the companion study of resource estimates for materials (cite when
public), downloads. Do not claim what is not yet true. -->

# AI usage disclosure

<!-- AUTHOR TO COMPLETE. Parts of the code, tests, and documentation were written with an AI
coding assistant (Claude Code) under the author's direction; state which, and how the author
reviewed and validated the output, as the JOSS policy requires. -->

# Acknowledgements

<!-- AUTHOR TO COMPLETE: funding and contributors. -->

# References
