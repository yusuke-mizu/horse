from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from horse_sim.db.models import FactorEffect, Race, RaceEntry
from horse_sim.factors.context import gate_band
from horse_sim.factors.stats import EffectEstimate, confidence_cap


EXPRESSION_SKIP = {"style_pace"}


@dataclass
class AppliedFactor:
    factor_name: str
    multiplier: float
    effect_size: float
    sample_size: int
    confidence: float
    reproducibility: float | None
    text: str
    used: bool


def apply_estimate(est: EffectEstimate, extra_text: str = "") -> AppliedFactor:
    cap = confidence_cap(est.sample_size, est.confidence)
    strength = cap * (est.reproducibility or 0.5)
    delta = est.effect_size * strength
    used = abs(delta) > 1e-6
    return AppliedFactor(
        factor_name=est.factor_name,
        multiplier=1.0 + delta,
        effect_size=est.effect_size,
        sample_size=est.sample_size,
        confidence=est.confidence,
        reproducibility=est.reproducibility,
        text=(
            f"{est.factor_name} {est.conditions}: 効果量 {est.effect_size:+.4f}, "
            f"平均残差 {est.mean_residual:+.2f}, サンプル {est.sample_size}, "
            f"信頼度 {est.confidence:.2f}, 再現性 {est.reproducibility:.2f}。"
            f"{'信頼度またはサンプル不足のため補正ほぼなし。' if not used else ''}"
            f"{extra_text}"
        ),
        used=used,
    )


def lookup_factors(session: Session, race: Race, entry: RaceEntry) -> list[AppliedFactor]:
    """DB 上の推定済み factor_effects（検査・テスト用）。予測は as_of 再推定を優先。"""
    applied: list[AppliedFactor] = []
    effects = session.query(FactorEffect).all()
    for fx in effects:
        if fx.factor_name in EXPRESSION_SKIP:
            continue
        try:
            conditions = json.loads(fx.conditions or "{}")
        except json.JSONDecodeError:
            conditions = {}
        if not _matches(conditions, race, entry):
            continue
        cap = confidence_cap(fx.sample_size, fx.confidence)
        strength = cap * (fx.reproducibility or 0.5)
        delta = fx.effect_size * strength
        used = abs(delta) > 1e-6
        applied.append(
            AppliedFactor(
                factor_name=fx.factor_name,
                multiplier=1.0 + delta,
                effect_size=fx.effect_size,
                sample_size=fx.sample_size,
                confidence=fx.confidence,
                reproducibility=fx.reproducibility,
                text=(
                    f"{fx.factor_name}: 効果量 {fx.effect_size:+.3f}, サンプル {fx.sample_size}, "
                    f"信頼度 {fx.confidence:.2f}, 再現性 {fx.reproducibility if fx.reproducibility is not None else 'n/a'}。"
                    f"{'今回は信頼度不足のため補正ほぼなし。' if not used else ''}"
                ),
                used=used,
            )
        )
    return applied


def population_for_entry(index, race: Race, entry: RaceEntry) -> list[AppliedFactor]:
    from horse_sim.factors.estimate import PopulationIndex

    index: PopulationIndex
    applied: list[AppliedFactor] = []
    going = index.going_effect(race.surface, race.track_condition)
    if going:
        applied.append(apply_estimate(going, extra_text=" 母集団の馬場残差（馬固有と併用時は縮小）。"))
    band = gate_band(entry.gate)
    gate = index.gate_effect(race.course, race.surface, band)
    if gate:
        applied.append(apply_estimate(gate, extra_text=f" 枠帯={band}。"))
    return applied


def _matches(conditions: dict, race: Race, entry: RaceEntry) -> bool:
    if not conditions:
        return True
    if "surface" in conditions and conditions["surface"] != race.surface:
        return False
    if "track_condition" in conditions and conditions["track_condition"] != race.track_condition:
        return False
    if "course" in conditions and conditions["course"] != race.course:
        return False
    if "gate_band" in conditions and conditions["gate_band"] != gate_band(entry.gate):
        return False
    if "running_style" in conditions and conditions["running_style"] != entry.running_style:
        return False
    if "pace_label" in conditions:
        return False
    return True


def merge_going(factors: list[AppliedFactor]) -> list[AppliedFactor]:
    """馬固有馬場が使えるときは母集団馬場を落とす（二重計上しない）。"""
    horse = [f for f in factors if f.factor_name == "horse_going" and f.used]
    if not horse:
        return factors
    return [f for f in factors if f.factor_name != "going"]


def combined_expression(factors: list[AppliedFactor], weight: float = 1.0) -> float:
    rate = 1.0
    for f in factors:
        if f.factor_name in EXPRESSION_SKIP:
            continue
        delta = (f.multiplier - 1.0) * weight
        rate *= 1.0 + delta
    return max(0.90, min(1.10, rate))
