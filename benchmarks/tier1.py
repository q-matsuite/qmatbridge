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
    "H": 1,   # H
    "Li": 3,  # Li_sv
    "O": 6,   # O
    "Mg": 8,  # Mg_pv
    "Si": 4,  # Si
    "Ti": 10,  # Ti_pv
    "Fe": 14,  # Fe_pv
}


@dataclass(frozen=True)
class BenchmarkSpec:
    key: str
    mp_id: str
    description: str
    cell_species: tuple[str, ...]  # expected primitive-cell sites
    spin_polarized: bool = False

    @property
    def expected_electrons(self) -> int:
        return sum(MP_VALENCE[el] for el in self.cell_species)

    @property
    def fixture_name(self) -> str:
        return f"{self.key}.json"


TIER1: tuple[BenchmarkSpec, ...] = (
    BenchmarkSpec("Si", "mp-149", "Diamond-cubic silicon", ("Si", "Si")),
    BenchmarkSpec("LiH", "mp-23703", "Rocksalt lithium hydride", ("Li", "H")),
    BenchmarkSpec("Fe", "mp-13", "BCC iron (magnetic)", ("Fe",), True),
    BenchmarkSpec("MgO", "mp-1265", "Rocksalt magnesium oxide", ("Mg", "O")),
    BenchmarkSpec(
        "TiO2",
        "mp-2657",
        "Rutile titanium dioxide",
        ("Ti", "Ti", "O", "O", "O", "O"),
    ),
)
