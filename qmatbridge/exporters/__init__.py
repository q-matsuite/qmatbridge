"""QMatBridge downstream exporters.

Each sub-module turns a :class:`~qmatbridge.schema.QMatEntry` into one
downstream format and reports it as :class:`~qmatbridge.schema.ExportMetadata`.
Exporters are registry plugins (see :mod:`qmatbridge.registry`).

Available exporters
-------------------
numpy_planewave
    Raw first-quantized plane-wave arrays (G-vectors, ions, structure factor)
    in a NumPy ``.npz`` archive.  Needs ``pip install qmatbridge[numpy]``.
openfermion
    Second-quantized plane-wave Hamiltonian as an OpenFermion
    ``InteractionOperator``.  Needs ``pip install qmatbridge[openfermion]``.
lcu
    The same Hamiltonian as a Pauli linear combination of unitaries (λ,
    coefficients, PREPARE probabilities) for qualtran / pyLIQTR / Cirq.
"""
