"""Rule-driven architecture for Escora.AI.

Import REGISTRY from here to access all registered rules and verifiers.
"""
from src.rules.schema import REGISTRY, Rule, RuleRegistry, Source, Violation

__all__ = ["REGISTRY", "Rule", "RuleRegistry", "Source", "Violation"]

# Register all verifiers on import
from src.rules.verifiers import register_all as _register_all

_register_all()
