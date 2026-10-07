# Upstream Adapters

Adapters are thin modules that map classical materials databases to the
QMatBridge neutral intermediate representation (`QMatEntry` /
`MaterialReference`).  Each adapter:

- Is importable without its optional dependency installed
- Raises `ImportError` with a clear install hint only when a live API call
  is made
- Captures full provenance in `SourceProvenance` so every entry is
  reproducible from its canonical hash

---

## Design contract

Every adapter must expose at minimum:

```python
def build_material_reference_from_<db>(
    material_id: str, **kwargs
) -> MaterialReference: ...          # no network call required

def fetch_structure_metadata_from_<db>(
    material_id: str, api_key: str | None = None, ...
) -> StructureMetadata: ...          # live API call
```

The split between "build from known data" and "fetch from API" is
intentional: it lets downstream code construct provenance stubs and
canonical hashes without network access, while keeping live fetchers
isolated and testable.

---

## Materials Project

| | |
| --- | --- |
| **Status** | Stub available — full implementation planned for v0.2 |
| **Module** | `qmatbridge.adapters.materials_project` |
| **Optional extra** | `pip install qmatbridge[mp]` (adds `mp-api`, `pymatgen`) |
| **Database** | https://materialsproject.org |
| **Coverage** | Inorganic crystals, ~160 k entries, DFT (PBE / r²SCAN) |

The Materials Project holds the broadest coverage of inorganic periodic
materials with open-access DFT data, making it the natural first adapter.

### Planned v0.2 scope

- `fetch_structure_metadata_from_mp` — lattice parameters, sites, spacegroup
  via `MPRester` from `mp-api`
- `fetch_hamiltonian_metadata_from_mp` — VASP INCAR/KPOINTS extraction,
  plane-wave cutoff, k-point mesh
- Plane-wave basis truncation utility: `num_plane_waves_from_ecut(ecut_ev, volume_ang3)`
- Coulomb operator in reciprocal space for kinetic + electron–nuclear terms

### Configuration

```python
from qmatbridge.adapters.materials_project import MPAdapterConfig

config = MPAdapterConfig(
    api_key="your-key",       # or set MP_API_KEY env var
    max_sites=20,             # skip large supercells
    timeout_s=60.0,
)
```

### Stub usage (no API key needed)

```python
from qmatbridge.adapters.materials_project import build_material_reference_from_mp

ref = build_material_reference_from_mp(
    "mp-149",
    formula="Si",
    spacegroup_number=227,
    spacegroup_symbol="Fd-3m",
    crystal_system="cubic",
)
print(ref.provenance.primary.identifier)   # "mp-149"
```

---

## OPTIMADE-compatible sources

| | |
| --- | --- |
| **Status** | Planned — v0.4 target |
| **Module** | `qmatbridge.adapters.optimade` (planned) |
| **Optional extra** | `pip install qmatbridge[optimade]` |
| **Spec** | https://www.optimade.org |

[OPTIMADE](https://www.optimade.org) is a REST API standard adopted by many
materials databases, including AFLOW, JARVIS, NOMAD, and MC3D.  A single
adapter targeting the OPTIMADE spec covers all compliant sources.

### Planned scope

- Generic `OptimadeAdapterConfig` with `base_url` and optional `api_key`
- `fetch_structure_metadata_from_optimade(entry_id, base_url)` using only
  the standard OPTIMADE `/structures/{id}` endpoint
- Pre-configured convenience wrappers for common providers:

| Provider | Base URL |
| --- | --- |
| AFLOW | `https://aflow.org/API/optimade/` |
| JARVIS | `https://jarvis.nist.gov/optimade` |
| NOMAD | `https://nomad-lab.eu/prod/v1/api/optimade` |
| MC3D | `https://mc3d.materialscloud.org/optimade/v1` |

---

## Alexandria

| | |
| --- | --- |
| **Status** | Planned — v0.4 target |
| **Module** | `qmatbridge.adapters.alexandria` (planned) |
| **Optional extra** | `pip install qmatbridge[alexandria]` |
| **Database** | https://alexandria.icams.rub.de |

The [Alexandria library](https://alexandria.icams.rub.de) provides ~4.5 M
DFT-relaxed structures computed with PBEsol, HSE06, and r²SCAN functionals —
significantly larger than MP for systematic benchmarking of functional
dependence in Hamiltonian norms.

### Why Alexandria matters for QMatBridge

- **Functional diversity**: PBEsol and HSE06 structures alongside PBE allow
  cross-functional benchmarks of LCU norms (λ) and plane-wave counts.
- **Scale**: order-of-magnitude more entries than MP enables statistical
  studies of resource-estimation trends across chemistry.
- **OPTIMADE compliance**: Alexandria exposes an OPTIMADE endpoint, so the
  OPTIMADE adapter may cover it automatically once that adapter is complete.

### Planned scope

- `AlexandriaAdapterConfig` with functional selector
  (`"PBEsol"`, `"HSE06"`, `"r2SCAN"`)
- `fetch_structure_metadata_from_alexandria(material_id, functional)`
- Cross-reference between Alexandria IDs and MP IDs via shared ICSD numbers

---

## OQMD (Open Quantum Materials Database)

| | |
| --- | --- |
| **Status** | Live fetch implemented (registry name `oqmd`); tested against recorded responses |
| **Module** | `qmatbridge.adapters.oqmd` |
| **Dependencies** | none: standard-library HTTP, no API key |
| **Database** | [oqmd.org](https://oqmd.org) |
| **Coverage** | ~1 M inorganic structures, DFT (PBE / VASP) |

```python
from qmatbridge.registry import get_adapter

entry = get_adapter("oqmd").fetch_entry("oqmd-1214579")   # or 1214579
```

Entry IDs are integers; QMatBridge stores them as `"oqmd-1214579"`.

### What is fetched and what is assumed

The OQMD REST API returns the relaxed cell, the atomic sites and the spacegroup
*symbol*. It does **not** return the calculation settings. QMatBridge therefore
records, under `hamiltonian.metadata["assumed"]`, three things that come from
configuration rather than from the database:

| Field | Default | Override |
| --- | --- | --- |
| `cutoff_energy_ev` | 520 eV (OQMD's published protocol) | `OQMDAdapterConfig(encut_ev=...)` |
| `spin_polarized` | `True` | `OQMDAdapterConfig(spin_polarized=...)` |
| `valence_charges` | built-in table for H, He, C, N, O, F, Ne, Si, P, S, Cl, Ar | `OQMDAdapterConfig(valence_charges={"Na": 7})` |

Elements outside the table have several PAW potentials with different valence
counts, so the adapter **refuses** rather than guesses; pass the charge of the
potential you mean. The spacegroup *number* is not in the API and stays unset.

### Configuration

```python
from qmatbridge.adapters.oqmd import OQMDAdapterConfig

config = OQMDAdapterConfig(
    max_sites=20,                       # refuse large supercells
    timeout_s=60.0,
    retries=3,                          # transient 5xx / network errors, doubling backoff
    valence_charges={"Li": 3, "Co": 17},
)
```

The OQMD server returns an HTML error page when overloaded; the adapter treats
that as transient and retries. `http_get=` replaces the transport, which is how
the unit tests replay recorded responses.

### Provenance-only reference (no network)

```python
from qmatbridge.adapters.oqmd import build_material_reference_from_oqmd

ref = build_material_reference_from_oqmd(1214579, formula="Si")
print(ref.provenance.primary.identifier)  # "oqmd-1214579"
```

---

## Adapter registry (future)

Once multiple adapters are stable, QMatBridge will expose a simple registry
so callers can fetch by database name without importing each adapter
explicitly:

```python
# Future API — not yet available
from qmatbridge.adapters import fetch

ref = fetch("mp-149", db="materials_project", api_key="...")
ref = fetch("aflow:AFLOW-2024-abc", db="aflow")
```

Community adapters (ICSD, COD, CCSD) can register themselves via a
`qmatbridge.adapters` entry-point group in their own packages.
