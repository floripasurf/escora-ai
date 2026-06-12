"""Rule verifiers registration.

Each domain module (geom.py, load.py, etc.) defines rules and their
verifier functions. register_all() is called once from src.rules.__init__
to populate the global REGISTRY.
"""

_registered = False


def register_all() -> None:
    """Register all verifier modules. Idempotent."""
    global _registered
    if _registered:
        return
    _registered = True

    from src.rules.verifiers import geom
    from src.rules.verifiers import load
    from src.rules.verifiers import space
    from src.rules.verifiers import struct
    from src.rules.verifiers import equip
    from src.rules.verifiers import env
    from src.rules.verifiers import operational  # OP-001 a OP-017 (manual §17)
    from src.rules.verifiers import reescoramento  # DECIDE-001/002 (manual §26)
    from src.rules.verifiers import audit  # AUDIT-001/002 (inspecao automatica do revisor)
