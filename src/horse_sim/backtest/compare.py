from __future__ import annotations

from sqlalchemy.orm import Session

from horse_sim.backtest.split import summarize_win_probs
from horse_sim.db.models import HorsePerformance, ModelVersion, Race
from horse_sim.factors.estimate import PHASE2_VERSION
from horse_sim.pipeline import fit_abilities, predict_race


def compare_ability_vs_phase2(session: Session, *, limit: int = 12, draws: int = 250) -> dict:
    fit_abilities(session)
    races = session.query(Race).order_by(Race.date.desc()).limit(limit).all()
    races = list(reversed(races))
    out = {}
    for use_factors, code in ((False, "ability_v1"), (True, PHASE2_VERSION)):
        probs: list[float] = []
        wins: list[int] = []
        for race in races:
            pred = predict_race(
                session,
                race.id,
                draws=draws,
                use_condition_factors=use_factors,
                persist=False,
                model_code=code,
            )
            for h in pred.horses:
                actual = (
                    session.query(HorsePerformance)
                    .filter_by(race_id=race.id, horse_id=h["horse_id"])
                    .one_or_none()
                )
                if actual is None or actual.finish_position is None:
                    continue
                probs.append(h["p_win"])
                wins.append(1 if actual.finish_position == 1 else 0)
        summary = summarize_win_probs(probs, wins)
        row = session.query(ModelVersion).filter_by(code=code).one_or_none()
        if row is None:
            row = ModelVersion(code=code, description=code)
            session.add(row)
        row.brier = summary["brier"]
        row.log_loss = summary["log_loss"]
        session.commit()
        out[code] = summary
    return out
