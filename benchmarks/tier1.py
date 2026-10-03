"""Tier-1 benchmark materials: specification and consistency checks.

Each :class:`BenchmarkSpec` records what we *expect* from the Materials
Project record (formula, cell size, valence electrons).  Expected electron
counts are derived from the default MP VASP POTCAR valences in
:data:`MP_VALENCE`, not hand-typed, so the spec is checkable.

``build_tier1_fixtures.py`` compares live MP data against these specs and
refuses to write a fixture whose formula, site count or electron count
disagrees.  MP IDs below are the intended targets and are verified at
generation time.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Valence electrons per atom for the default MP (MPRelaxSet) POTCARs.
MP_VALENCE: dict[str, int] = {
    "H": 1,    # H
    "Li": 3,   # Li_sv
    "N": 5,    # N
    "O": 6,    # O
    "Mg": 8,   # Mg_pv
    "Si": 4,   # Si
    "Ti": 10,  # Ti_pv
    "Co": 9,   # Co
    "Fe": 14,  # Fe_pv
    "Ga": 13,  # Ga_d
}


@dataclass(frozen=True)
class BenchmarkSpec:
    key: str
    label: str
    mp_id: str
    description: str
    category: str
    cell_species: tuple[str, ...]  # expected primitive-cell sites
    spin_polarized: bool = False

    @property
    def expected_electrons(self) -> int:
        return sum(MP_VALENCE[el] for el in self.cell_species)

    @property
    def fixture_name(self) -> str:
        return f"{self.key}.json"


#: Initial examples: a textbook semiconductor, a wide-gap III-V, and a Li-ion
#: battery cathode.  More materials are listed in ``PLANNED``.
TIER1: tuple[BenchmarkSpec, ...] = (
    BenchmarkSpec(
        "Si", "Si", "mp-149", "Diamond-cubic silicon", "semiconductor",
        ("Si", "Si"),
    ),
    BenchmarkSpec(
        "GaN", "GaN", "mp-804", "Wurtzite gallium nitride", "wide-gap III-V",
        ("Ga", "Ga", "N", "N"),
    ),
    BenchmarkSpec(
        "LiCoO2", "LiCoO\u2082", "mp-22526",
        "Layered LiCoO\u2082, the classic Li-ion cathode", "battery cathode",
        ("Li", "Co", "O", "O"), True,
    ),
)

#: Candidate follow-ups (not yet specified in detail): (key, mp_id, note).
PLANNED: tuple[tuple[str, str, str], ...] = (
    ("LiH", "mp-23703", "small system with exact-diagonalisation reference"),
    ("Fe", "mp-13", "BCC iron, magnetic"),
    ("MgO", "mp-1265", "ionic, wide gap"),
    ("TiO2", "mp-2657", "rutile, d-electron system"),
)
