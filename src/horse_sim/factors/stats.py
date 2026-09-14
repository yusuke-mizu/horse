from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class EffectEstimate:
    factor_name: str
    conditions: dict
    effect_size: float
    sample_size: int
    confidence: float
    reproducibility: float
    statistical_significance: float
    mean_residual: float
    notes: str = ""

    @property
    def direction(self) -> str:
        if self.effect_size > 1e-4:
            return "plus"
        if self.effect_size < -1e-4:
            return "minus"
        return "none"


def residual_stats(values: list[float]) -> tuple[float, float, int]:
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0
    mean = sum(values) / n
    if n == 1:
        return mean, 0.0, 1
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(max(var, 0.0)), n


def t_confidence(mean: float, sd: float, n: int) -> tuple[float, float]:
    """信頼度と |t| 由来の粗い有意性。因果主張には使わない。"""
    if n < 3 or sd <= 1e-9:
        return 0.0, 0.0
    se = sd / math.sqrt(n)
    t = abs(mean) / se
    conf = 1.0 - math.exp(-0.5 * min(t, 8.0) ** 2)
    p_proxy = math.exp(-0.5 * min(t, 8.0) ** 2)
    return conf, 1.0 - p_proxy


def split_reproducibility(first: list[float], second: list[float]) -> float:
    if len(first) < 15 or len(second) < 15:
        return 0.5
    m1 = sum(first) / len(first)
    m2 = sum(second) / len(second)
    if abs(m1) < 1e-6 and abs(m2) < 1e-6:
        return 0.7
    same = (m1 >= 0 and m2 >= 0) or (m1 < 0 and m2 < 0)
    mag = min(abs(m1), abs(m2)) / max(abs(m1), abs(m2), 1e-9)
    return (0.65 if same else 0.25) * (0.5 + 0.5 * mag)


def confidence_cap(sample_size: int, confidence: float) -> float:
    """少数サンプルの効果を強く掛けない。"""
    if sample_size < 30:
        return 0.0
    if sample_size < 150:
        return min(confidence, 0.35) * (sample_size / 150.0)
    return min(confidence, 1.0)


def from_residuals(
    factor_name: str,
    conditions: dict,
    residuals: list[float],
    *,
    notes: str = "",
) -> EffectEstimate:
    mean, sd, n = residual_stats(residuals)
    conf, sig = t_confidence(mean, sd, n)
    mid = n // 2
    repro = split_reproducibility(residuals[:mid], residuals[mid:]) if n else 0.5
    return EffectEstimate(
        factor_name=factor_name,
        conditions=conditions,
        effect_size=mean / 100.0,
        sample_size=n,
        confidence=conf,
        reproducibility=repro,
        statistical_significance=sig,
        mean_residual=mean,
        notes=notes or "効果なしも含めて保存。相関を因果とは書かない。",
    )
