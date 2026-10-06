# API keys and data licences

**QMatBridge never ships, stores or proxies credentials.** If an upstream database needs
a key, you create your own account, get your own key, and supply it. Nothing in this
repository, its CI, or its website contains one.

## Which sources need a key

| Source | Key needed? | Notes |
| --- | --- | --- |
| Materials Project | **Yes** (free) | Create an account and copy your key from the [API page](https://next-gen.materialsproject.org/api) |
| OQMD | Not for the public REST API, to my knowledge | Adapter is a stub today; check OQMD's current terms |
| OPTIMADE providers | Provider-specific | Planned adapter (v0.4); many are open |

Check each provider's own terms before relying on this table; they can change.

## Supplying a Materials Project key

The adapter looks for a key in this order and uses the first it finds:

1. the `api_key=` argument of a fetch function;
2. `MPAdapterConfig(api_key=...)`;
3. the `MP_API_KEY` environment variable (the same variable `mp-api` itself reads).

```bash
export MP_API_KEY=...    # in your shell profile or secret manager, not in code
```

```python
from qmatbridge.adapters.materials_project import fetch_entry_from_mp

entry = fetch_entry_from_mp("mp-149")      # picks the key up from the environment
```

!!! warning "Keep keys out of git"
    Never put a key in source, notebooks, `.gitignore` (a tracked file) or issue
    comments. For local development, keep it in a `.env` file: the repository's
    `.gitignore` already excludes `.env` and `.env.*`, and `.env.example` shows the
    format. The benchmark fixture builder reads `.env` automatically; the library
    itself only reads the environment variable. If a key is ever exposed, regenerate it
    on the provider's site.

## Do I need a key to use the benchmarks?

No, once fixtures are committed: the Tier-1 entries are plain JSON, so reading and
comparing them needs no network access. A key is needed only to **fetch new materials**
or to **regenerate** the fixtures (`python -m benchmarks.build_tier1_fixtures`).

## Data licences and attribution

Records fetched from a database remain subject to that database's licence. Materials
Project data is released under **CC BY 4.0**: if you redistribute entries, fixtures or
figures derived from it, credit the Materials Project. Each `QMatEntry` carries its
source in `reference.provenance`, so attribution travels with the data. The QMatBridge
code itself is MIT-licensed; that does not relicense upstream data.
