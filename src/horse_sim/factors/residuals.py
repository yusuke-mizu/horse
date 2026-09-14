from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from horse_sim.config import settings
from horse_sim.db.models import HorsePerformance, RaceResult
from horse_sim.factors.context import normalize_pace
from horse_sim.normalize.pipeline import assert_no_future_leak


@dataclass
class ResidualRow:
    date: date
    race_id: int
    horse_id: int
    residual: float
    going: str | None
    surface: str
    course: str
    distance: int
    gate: int | None
    style: str | None
    pace: str | None


def collect_residuals(session: Session, as_of: date) -> list[ResidualRow]:
    perfs = (
        session.query(HorsePerformance)
        .filter(
            HorsePerformance.date < as_of,
            HorsePerformance.adjusted_performance.isnot(None),
        )
        .order_by(HorsePerformance.date.asc(), HorsePerformance.race_id.asc())
        .all()
    )
    assert_no_future_leak(as_of, [p.date for p in perfs])
    pace_by_race: dict[int, str | None] = {}
    for result in session.query(RaceResult).all():
        pace_by_race[result.race_id] = normalize_pace(result.pace_label)

    by_race: dict[int, list[HorsePerformance]] = defaultdict(list)
    for p in perfs:
        by_race[p.race_id].append(p)

    pre: dict[int, float] = defaultdict(lambda: settings.ability_prior)
    rows: list[ResidualRow] = []
    ordered = sorted(by_race, key=lambda rid: (by_race[rid][0].date, rid))
    for race_id in ordered:
        field = by_race[race_id]
        race_pace = pace_by_race.get(race_id) or normalize_pace(field[0].pace)
        for p in field:
            pre_ab = pre[p.horse_id]
            residual = (p.adjusted_performance or settings.ability_prior) - pre_ab
            rows.append(
                ResidualRow(
                    date=p.date,
                    race_id=race_id,
                    horse_id=p.horse_id,
                    residual=residual,
                    going=p.track_condition,
                    surface=p.surface,
                    course=p.course,
                    distance=p.distance,
                    gate=p.gate,
                    style=None,
                    pace=race_pace,
                )
            )
        for p in field:
            if p.estimated_ability is not None:
                pre[p.horse_id] = p.estimated_ability
    # style lives on entries / running_style; fill from race entries if missing
    if rows:
        from horse_sim.db.models import RaceEntry

        styles = {
            (e.race_id, e.horse_id): e.running_style
            for e in session.query(RaceEntry).all()
        }
        for row in rows:
            if not row.style:
                row.style = styles.get((row.race_id, row.horse_id))
    return rows
