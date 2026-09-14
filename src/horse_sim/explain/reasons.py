from __future__ import annotations

from horse_sim.ability.as_of import HorseAbility
from horse_sim.factors.engine import AppliedFactor


def confidence_label(n_starts: int, sd: float) -> str:
    if n_starts >= 8 and sd <= 2.2:
        return "高"
    if n_starts >= 4:
        return "中"
    return "低"


def build_explanations(
    horse_name: str,
    ability: HorseAbility,
    factors: list[AppliedFactor],
    expression: float,
) -> list[dict]:
    rows: list[dict] = []
    rows.append(
        {
            "kind": "method",
            "factor_name": "base_ability",
            "magnitude": ability.base_ability,
            "sample_size": ability.n_starts,
            "confidence": 1.0 - ability.shrinkage,
            "text": (
                f"{horse_name} の基礎能力 {ability.base_ability:.1f} は、"
                f"出走日より前の {ability.n_starts} 走の補正パフォーマンスの指数加重平均。"
                f"事前分布への縮小率 {ability.shrinkage:.2f}。"
                f"{'サンプル不足のため事前100点へ強く縮小。' if ability.n_starts < 4 else ''}"
            ),
        }
    )
    used = [f for f in factors if f.used]
    unused_weak = [f for f in factors if not f.used]
    if not used:
        rows.append(
            {
                "kind": "method",
                "factor_name": "expression_rate",
                "magnitude": expression,
                "sample_size": 0,
                "confidence": 0.0,
                "text": (
                    "今回発揮率は Phase 1 では推定済み factor_effects が無いため 100% 近傍。"
                    "馬場・血統・騎手などの固定加点は適用していない。"
                ),
            }
        )
    for f in used:
        kind = "plus" if f.multiplier > 1.0 else "minus"
        rows.append(
            {
                "kind": kind,
                "factor_name": f.factor_name,
                "magnitude": f.effect_size,
                "sample_size": f.sample_size,
                "confidence": f.confidence,
                "text": f.text,
            }
        )
    for f in unused_weak:
        rows.append(
            {
                "kind": "weak",
                "factor_name": f.factor_name,
                "magnitude": f.effect_size,
                "sample_size": f.sample_size,
                "confidence": f.confidence,
                "text": f.text,
            }
        )
    return rows
