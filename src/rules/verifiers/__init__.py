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
