from __future__ import annotations

import math
from datetime import date

from sqlalchemy.orm import Session

from horse_sim.db.models import HorsePerformance, Race, RaceEntry
from horse_sim.factors.engine import AppliedFactor
from horse_sim.factors.stats import t_confidence
from horse_sim.normalize.pipeline import assert_no_future_leak


def _factor(
    name: str,
    effect: float,
    n: int,
    conf: float,
    text: str,
    used: bool,
    repro: float = 0.5,
) -> AppliedFactor:
    strength_n = 0.0 if n < 4 else min(1.0, n / 12.0)
    delta = effect * strength_n * max(conf, 0.15) if used else 0.0
    if n < 4:
        used = False
        delta = 0.0
    return AppliedFactor(
        factor_name=name,
        multiplier=1.0 + delta,
        effect_size=effect,
        sample_size=n,
        confidence=conf,
        reproducibility=repro,
        text=text,
        used=used and abs(delta) > 1e-6,
    )


def horse_condition_factors(
    session: Session,
    race: Race,
    entry: RaceEntry,
    as_of: date,
    past: list[HorsePerformance],
) -> list[AppliedFactor]:
    assert_no_future_leak(as_of, [p.date for p in past])
    scored = [p for p in past if p.adjusted_performance is not None]
    out: list[AppliedFactor] = []
    out.append(_distance_curve(scored, race.distance))
    out.append(_match_mean(scored, "horse_going", "馬場", lambda p: p.track_condition == race.track_condition, race.track_condition or "不明"))
    out.append(_match_mean(scored, "horse_course", "コース", lambda p: p.course == race.course, race.course))
    return out


def _distance_curve(past: list[HorsePerformance], target: int) -> AppliedFactor:
    pairs = [(p.distance, p.adjusted_performance or 0.0) for p in past]
    n = len(pairs)
    if n == 0:
        return _factor(
            "horse_distance",
            0.0,
            0,
            0.0,
            "距離適性: 当該走以前の走なし。補正なし。",
            False,
        )
    overall = sum(y for _, y in pairs) / n
    bandwidth = 250.0
    wsum = 0.0
    xsum = 0.0
    for d, y in pairs:
        w = math.exp(-(((d - target) / bandwidth) ** 2))
        wsum += w
        xsum += w * y
    kernel = xsum / wsum if wsum > 1e-9 else overall
    effect = (kernel - overall) / 100.0
    conf, _ = t_confidence(kernel - overall, 2.5, n)
    used = wsum >= 2.5 and n >= 4
    return _factor(
        "horse_distance",
        effect,
        n,
        conf,
        (
            f"距離適性: 今回{target}mでのカーネル平均 {kernel:.1f}、"
            f"自己平均 {overall:.1f}、有効重み {wsum:.1f}、サンプル {n}。"
            f"{'サンプル不足のため補正なし。' if not used else ''}"
        ),
        used,
    )


def _match_mean(
    past: list[HorsePerformance],
    name: str,
    label: str,
    pred,
    key: str,
) -> AppliedFactor:
    all_p = [p.adjusted_performance or 0.0 for p in past]
    matched = [p.adjusted_performance or 0.0 for p in past if pred(p)]
    n = len(matched)
    if not all_p:
        return _factor(name, 0.0, 0, 0.0, f"{label}適性: データなし。", False)
    overall = sum(all_p) / len(all_p)
    if n == 0:
        return _factor(
            name,
            0.0,
            0,
            0.0,
            f"{label}適性: {key} での過去走なし。補正なし。",
            False,
        )
    m = sum(matched) / n
    effect = (m - overall) / 100.0
    conf, _ = t_confidence(m - overall, 2.5, n)
    used = n >= 4
    return _factor(
        name,
        effect,
        n,
        conf,
        (
            f"{label}適性: {key} 平均 {m:.1f} vs 自己平均 {overall:.1f}、サンプル {n}。"
            f"{'サンプル不足のため補正なし。' if not used else ''}"
        ),
        used,
    )
