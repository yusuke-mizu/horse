from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from horse_sim.db.models import (
    DataSource,
    Horse,
    HorsePerformance,
    Jockey,
    Race,
    RaceEntry,
    RaceResult,
    Trainer,
)
from horse_sim.ingestion.base import IngestReport

COURSES = ["京都", "阪神", "東京", "中山"]
DISTANCES = [1200, 1400, 1600, 1800, 2000]
CONDITIONS = ["良", "稍重", "重", "不良"]
STYLES = ["逃げ", "先行", "差し", "追込"]


def _true_time(true_ability: float, distance: int, noise: float) -> float:
    par = distance / 16.4
    return par - (true_ability - 100.0) * 0.22 + noise


def ingest_synthetic(
    session: Session,
    *,
    n_horses: int = 80,
    n_race_days: int = 40,
    races_per_day: int = 4,
    seed: int = 42,
    start: date = date(2022, 1, 1),
) -> IngestReport:
    """パイプライン検証用の合成データ。実開催の成績ではない。"""
    rng = random.Random(seed)
    now = datetime.utcnow()
    horses: list[Horse] = []
    true_ability: dict[int, float] = {}
    style_of: dict[int, str] = {}

    for i in range(n_horses):
        horse = Horse(
            name=f"シンセティック{i+1:03d}",
            sex=rng.choice(["牡", "牝", "セ"]),
            birth_year=2018 + (i % 5),
            sire=f"父系統{i % 12}",
            damsire=f"母父系統{i % 9}",
        )
        session.add(horse)
        session.flush()
        horses.append(horse)
        true_ability[horse.id] = rng.gauss(100.0, 3.2)
        style_of[horse.id] = STYLES[i % 4]

    jockeys = []
    trainers = []
    for i in range(16):
        j = Jockey(name=f"騎手{i+1:02d}")
        t = Trainer(name=f"調教師{i+1:02d}")
        session.add_all([j, t])
        session.flush()
        jockeys.append(j)
        trainers.append(t)

    race_count = 0
    entry_count = 0
    for day_i in range(n_race_days):
        d = start + timedelta(days=day_i * 7)
        course = COURSES[day_i % len(COURSES)]
        for rn in range(1, races_per_day + 1):
            surface = "turf" if rn % 2 else "dirt"
            distance = DISTANCES[(day_i + rn) % len(DISTANCES)]
            going = CONDITIONS[0] if rng.random() < 0.7 else rng.choice(CONDITIONS)
            race = Race(
                date=d,
                course=course,
                surface=surface,
                distance=distance,
                track_condition=going,
                weather="晴",
                race_name=f"{course}{rn}R",
                race_number=rn,
                class_code="合成",
                source="synthetic",
                source_fetched_at=now,
                quality_score=1.0,
            )
            session.add(race)
            session.flush()
            race_count += 1
            field = rng.sample(horses, k=min(12, len(horses)))
            times: list[tuple[Horse, float, float]] = []
            for horse in field:
                noise = rng.gauss(0.0, 0.35)
                t = _true_time(true_ability[horse.id], distance, noise)
                times.append((horse, t, noise))
            times.sort(key=lambda x: x[1])
            winner_t = times[0][1]
            session.add(RaceResult(race_id=race.id, winning_time=round(winner_t, 1), pace_label="平均"))
            for pos, (horse, t, _) in enumerate(times, start=1):
                jk = rng.choice(jockeys)
                tr = rng.choice(trainers)
                margin = round((t - winner_t) * 5.0, 1)
                implied_odds = max(1.3, rng.uniform(1.5, 40.0) * (0.4 + 0.08 * pos))
                entry = RaceEntry(
                    race_id=race.id,
                    horse_id=horse.id,
                    jockey_id=jk.id,
                    trainer_id=tr.id,
                    gate=pos if pos <= 12 else 12,
                    weight=55.0 + (hash(horse.name) % 5),
                    body_weight=460 + (horse.id % 40),
                    body_weight_change=rng.choice([-8, -4, 0, 2, 6]),
                    odds=round(implied_odds, 1),
                    popularity=pos,
                    running_style=style_of[horse.id],
                )
                session.add(entry)
                entry_count += 1
                session.add(
                    HorsePerformance(
                        horse_id=horse.id,
                        race_id=race.id,
                        date=d,
                        course=course,
                        surface=surface,
                        distance=distance,
                        track_condition=going,
                        gate=entry.gate,
                        weight=entry.weight,
                        body_weight=entry.body_weight,
                        body_weight_change=entry.body_weight_change,
                        jockey=jk.name,
                        finish_position=pos,
                        finish_time=round(t, 1),
                        last_3f=round(33.5 + rng.gauss(0, 0.6), 1),
                        margin=margin,
                        class_code="合成",
                    )
                )

    src = DataSource(
        name="synthetic",
        fetched_at=now,
        missing_rate=0.0,
        duplicate_rate=0.0,
        quality_score=1.0,
        trust=0.3,
        notes="合成データ。実開催ではない。品質スコアは欠損の少なさであり、予測妥当性ではない。",
    )
    session.add(src)
    session.commit()
    return IngestReport(
        source="synthetic",
        fetched_at=now,
        races=race_count,
        entries=entry_count,
        missing_rate=0.0,
        duplicate_rate=0.0,
        quality_score=1.0,
        notes=src.notes,
    )


def implied_market_prob(odds: float | None) -> float | None:
    if not odds or odds <= 1.0:
        return None
    return 1.0 / odds
