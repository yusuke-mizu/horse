from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt

from sqlalchemy.orm import Session

from horse_sim.config import settings
from horse_sim.db.models import HorsePerformance
from horse_sim.normalize.pipeline import assert_no_future_leak


@dataclass
class HorseAbility:
    horse_id: int
    base_ability: float
    ability_sd: float
    n_starts: int
    last_date: date | None
    shrinkage: float


def ability_as_of(session: Session, horse_id: int, as_of: date) -> HorseAbility:
    rows = (
        session.query(HorsePerformance)
        .filter(
            HorsePerformance.horse_id == horse_id,
            HorsePerformance.date < as_of,
            HorsePerformance.adjusted_performance.isnot(None),
        )
        .order_by(HorsePerformance.date.asc())
        .all()
    )
    assert_no_future_leak(as_of, [r.date for r in rows])
    k = settings.ability_prior_strength
    if not rows:
        return HorseAbility(horse_id, settings.ability_prior, 3.5, 0, None, 1.0)
    # exponentially weighted mean of adjusted performances
    w_sum = 0.0
    x_sum = 0.0
    decay = 0.85
    weight = 1.0
    xs: list[float] = []
    for r in reversed(rows):
        x = r.adjusted_performance or settings.ability_prior
        xs.append(x)
        x_sum += weight * x
        w_sum += weight
        weight *= decay
    mean = x_sum / w_sum
    n = len(rows)
    shrink = k / (n + k)
    base = (1.0 - shrink) * mean + shrink * settings.ability_prior
    if len(xs) >= 2:
        m = sum(xs) / len(xs)
        var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
        sd = sqrt(var)
    else:
        sd = 2.8
    sd = max(0.8, sd) * sqrt(1.0 + shrink)
    return HorseAbility(horse_id, round(base, 3), round(sd, 3), n, rows[-1].date, round(shrink, 3))
