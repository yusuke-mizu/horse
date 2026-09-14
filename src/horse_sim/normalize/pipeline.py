from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from horse_sim.db.models import HorsePerformance, Race, RaceEntry


def normalize_performances(session: Session) -> int:
    """エントリー＋結果から horse_performances を補完する。能力値はまだ計算しない。"""
    created = 0
    entries = session.query(RaceEntry).all()
    existing = {
        (p.horse_id, p.race_id)
        for p in session.query(HorsePerformance.horse_id, HorsePerformance.race_id).all()
    }
    for entry in entries:
        key = (entry.horse_id, entry.race_id)
        if key in existing:
            continue
        race = session.get(Race, entry.race_id)
        if race is None:
            continue
        session.add(
            HorsePerformance(
                horse_id=entry.horse_id,
                race_id=entry.race_id,
                date=race.date,
                course=race.course,
                surface=race.surface,
                distance=race.distance,
                track_condition=race.track_condition,
                weather=race.weather,
                gate=entry.gate,
                weight=entry.weight,
                body_weight=entry.body_weight,
                body_weight_change=entry.body_weight_change,
                class_code=race.class_code,
            )
        )
        created += 1
        existing.add(key)
    session.commit()
    return created


def assert_no_future_leak(as_of: date, used_dates: list[date]) -> None:
    if any(d >= as_of for d in used_dates):
        raise ValueError("Time leak: performance dated on or after as_of was used for prediction.")
