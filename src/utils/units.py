"""Utilitários de conversão de unidades."""


def cm_to_m(value: float) -> float:
    return value / 100.0


def mm_to_m(value: float) -> float:
    return value / 1000.0


def m_to_cm(value: float) -> float:
    return value * 100.0


def kn_to_kgf(value: float) -> float:
    return value * 101.9716


def kgf_to_kn(value: float) -> float:
    return value / 101.9716
