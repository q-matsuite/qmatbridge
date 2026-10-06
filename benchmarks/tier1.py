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
    "Na": 7,   # Na_pv
    "Cl": 7,   # Cl
    "Ba": 10,  # Ba_sv
    "P": 5,    # P
}


@dataclass(frozen=True)
class BenchmarkSpec:
    key: str
    label: str
    mp_id: str
    description: str
    category: str
    cell_species: tuple[str, ...]  # expected primitive-cell sites
    functional: str = "PBE"
    #: Materials Project runs every calculation with ISPIN=2, including
    #: non-magnetic materials, so this is True throughout (verified live).
    spin_polarized: bool = True

    @property
    def expected_electrons(self) -> int:
        return sum(MP_VALENCE[el] for el in self.cell_species)

    @property
    def cell_formula(self) -> str:
        """Unit-cell formula in first-appearance order, e.g. ``Ga2N2``."""
        order = list(dict.fromkeys(self.cell_species))
        return "".join(
            el + (str(n) if (n := self.cell_species.count(el)) > 1 else "")
            for el in order
        )

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
        ("Li", "Co", "O", "O"), functional="PBE+U",
    ),
    BenchmarkSpec(
        "LiFePO4", "LiFePO\u2084", "mp-19017",
        "Olivine LiFePO\u2084, a 28-atom Li-ion cathode", "battery cathode",
        ("Li",) * 4 + ("Fe",) * 4 + ("P",) * 4 + ("O",) * 16, functional="PBE+U",
    ),
    BenchmarkSpec(
        "NaCl", "NaCl", "mp-22862", "Rocksalt sodium chloride", "ionic crystal",
        ("Na", "Cl"),
    ),
    BenchmarkSpec(
        "BaTiO3", "BaTiO\u2083", "mp-5020", "Perovskite barium titanate",
        "perovskite", ("Ba", "Ti", "O", "O", "O"),
    ),
)

#: Candidate follow-ups (not yet specified in detail): (key, mp_id, note).
PLANNED: tuple[tuple[str, str, str], ...] = (
    ("LiH", "mp-23703", "small system with exact-diagonalisation reference"),
    ("Fe", "mp-13", "BCC iron, magnetic"),
    ("MgO", "mp-1265", "ionic, wide gap"),
    ("TiO2", "mp-2657", "rutile; this MP entry is a 12-site cell, verify before specifying"),
)
