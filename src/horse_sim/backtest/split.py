from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from horse_sim.db.models import Race
from horse_sim.probability.metrics import brier_win, calibration_bins, log_loss_win


@dataclass
class TimeSplit:
    train_end: date
    validate_end: date | None
    test_start: date


def default_split() -> TimeSplit:
    return TimeSplit(train_end=date(2023, 12, 31), validate_end=date(2024, 12, 31), test_start=date(2025, 1, 1))


def races_in_range(session: Session, start: date, end: date) -> list[Race]:
    return (
        session.query(Race)
        .filter(Race.date >= start, Race.date <= end)
        .order_by(Race.date.asc())
        .all()
    )


def summarize_win_probs(probs: list[float], wins: list[int]) -> dict:
    return {
        "brier": brier_win(probs, wins),
        "log_loss": log_loss_win(probs, wins),
        "calibration": calibration_bins(probs, wins),
        "n": len(probs),
    }
