from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from horse_sim.db.models import Race, RaceEntry, RaceResult
from horse_sim.factors.context import normalize_pace


PACE_SCENARIOS = ("slow", "normal", "fast")


@dataclass
class PacePrior:
    slow: float
    normal: float
    fast: float

    def as_pairs(self) -> list[tuple[str, float]]:
        return [("slow", self.slow), ("normal", self.normal), ("fast", self.fast)]


def front_fraction(entries: list[RaceEntry]) -> float:
    n = max(len(entries), 1)
    return sum(1 for e in entries if e.running_style in ("逃げ", "先行")) / n


def heuristic_pace_prior(entries: list[RaceEntry]) -> PacePrior:
    """脚質構成からの仮説事前。データが足りないときだけ使う。"""
    front = front_fraction(entries)
    fast = 0.18 + 0.35 * front
    slow = 0.22 + 0.25 * (1.0 - front)
    normal = max(0.15, 1.0 - fast - slow)
    total = slow + normal + fast
    return PacePrior(slow / total, normal / total, fast / total)


def empirical_pace_prior(session: Session, as_of: date, entries: list[RaceEntry]) -> PacePrior:
    target = front_fraction(entries)
    counts = defaultdict(int)
    n = 0
    races = session.query(Race).filter(Race.date < as_of).all()
    results = {r.race_id: r for r in session.query(RaceResult).all()}
    entries_all = session.query(RaceEntry).all()
    by_race: dict[int, list[RaceEntry]] = defaultdict(list)
    for e in entries_all:
        by_race[e.race_id].append(e)
    for race in races:
        result = results.get(race.id)
        label = normalize_pace(result.pace_label if result else None)
        if not label:
            continue
        frac = front_fraction(by_race.get(race.id, []))
        if abs(frac - target) > 0.18:
            continue
        counts[label] += 1
        n += 1
    if n < 30:
        return heuristic_pace_prior(entries)
    slow = counts["slow"] / n
    normal = counts["normal"] / n
    fast = counts["fast"] / n
    total = slow + normal + fast
    if total <= 0:
        return heuristic_pace_prior(entries)
    return PacePrior(slow / total, normal / total, fast / total)


def pace_prior_from_styles(entries: list[RaceEntry]) -> PacePrior:
    return heuristic_pace_prior(entries)
