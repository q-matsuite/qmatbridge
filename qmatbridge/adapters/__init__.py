"""QMatBridge upstream adapter modules.

Each sub-module maps one classical materials database to the QMatBridge
neutral intermediate representation (``QMatEntry`` / ``MaterialReference``).

Available adapters
------------------
materials_project
    Stub adapter for the Materials Project (mp-api).  Full API integration
    is planned for v0.2.

All adapters are importable without their optional dependencies installed;
a ``ImportError`` with a helpful install hint is raised only when the
database-specific client is actually called.
"""
