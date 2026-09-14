from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

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


REQUIRED_RACE_FIELDS = ("date", "course", "surface", "distance")
REQUIRED_ENTRY_FIELDS = ("race_key", "horse_name")


def _get_or_create(session: Session, model, **kwargs):
    inst = session.query(model).filter_by(**kwargs).one_or_none()
    if inst is None:
        inst = model(**kwargs)
        session.add(inst)
        session.flush()
    return inst


def ingest_csv(session: Session, races_path: Path, entries_path: Path, source: str = "csv") -> IngestReport:
    """races.csv と entries.csv を取り込む。未来情報の混入検査は正規化層で行う。"""
    race_by_key: dict[str, Race] = {}
    missing = 0
    total = 0
    now = datetime.utcnow()

    with races_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            total += 1
            if any(not row.get(f) for f in REQUIRED_RACE_FIELDS):
                missing += 1
                continue
            key = row.get("race_key") or f"{row['date']}-{row['course']}-{row.get('race_number') or total}"
            race = Race(
                date=date.fromisoformat(row["date"]),
                course=row["course"].strip(),
                surface=row["surface"].strip().lower(),
                distance=int(row["distance"]),
                track_condition=(row.get("track_condition") or None),
                weather=(row.get("weather") or None),
                race_name=(row.get("race_name") or None),
                race_number=int(row["race_number"]) if row.get("race_number") else None,
                class_code=(row.get("class_code") or None),
                source=source,
                source_fetched_at=now,
                quality_score=None,
            )
            session.add(race)
            session.flush()
            race_by_key[key] = race
            if row.get("winning_time"):
                session.add(
                    RaceResult(
                        race_id=race.id,
                        winning_time=float(row["winning_time"]),
                        pace_label=(row.get("pace_label") or None),
                    )
                )

    entries_n = 0
    with entries_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            total += 1
            if any(not row.get(f) for f in REQUIRED_ENTRY_FIELDS):
                missing += 1
                continue
            race = race_by_key.get(row["race_key"])
            if race is None:
                missing += 1
                continue
            horse = _get_or_create(session, Horse, name=row["horse_name"].strip())
            if row.get("sex"):
                horse.sex = row["sex"]
            if row.get("birth_year"):
                horse.birth_year = int(row["birth_year"])
            if row.get("sire"):
                horse.sire = row["sire"]
            jockey = _get_or_create(session, Jockey, name=row["jockey"].strip()) if row.get("jockey") else None
            trainer = _get_or_create(session, Trainer, name=row["trainer"].strip()) if row.get("trainer") else None
            entry = RaceEntry(
                race_id=race.id,
                horse_id=horse.id,
                jockey_id=jockey.id if jockey else None,
                trainer_id=trainer.id if trainer else None,
                gate=int(row["gate"]) if row.get("gate") else None,
                weight=float(row["weight"]) if row.get("weight") else None,
                body_weight=float(row["body_weight"]) if row.get("body_weight") else None,
                body_weight_change=float(row["body_weight_change"]) if row.get("body_weight_change") else None,
                odds=float(row["odds"]) if row.get("odds") else None,
                popularity=int(row["popularity"]) if row.get("popularity") else None,
                equipment=(row.get("equipment") or None),
                running_style=(row.get("running_style") or None),
            )
            session.add(entry)
            entries_n += 1
            finish_pos = int(row["finish_position"]) if row.get("finish_position") else None
            finish_time = float(row["finish_time"]) if row.get("finish_time") else None
            if finish_pos or finish_time:
                session.add(
                    HorsePerformance(
                        horse_id=horse.id,
                        race_id=race.id,
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
                        jockey=jockey.name if jockey else None,
                        finish_position=finish_pos,
                        finish_time=finish_time,
                        last_3f=float(row["last_3f"]) if row.get("last_3f") else None,
                        margin=float(row["margin"]) if row.get("margin") else None,
                        class_code=race.class_code,
                    )
                )

    missing_rate = missing / total if total else 1.0
    quality = max(0.0, 1.0 - missing_rate)
    source_row = session.query(DataSource).filter_by(name=source).one_or_none()
    if source_row is None:
        source_row = DataSource(name=source)
        session.add(source_row)
    source_row.fetched_at = now
    source_row.missing_rate = missing_rate
    source_row.duplicate_rate = 0.0
    source_row.quality_score = quality
    source_row.trust = quality
    source_row.notes = "CSV ingest. Values are not assumed correct."
    session.commit()
    return IngestReport(
        source=source,
        fetched_at=now,
        races=len(race_by_key),
        entries=entries_n,
        missing_rate=missing_rate,
        duplicate_rate=0.0,
        quality_score=quality,
        notes=source_row.notes,
    )
