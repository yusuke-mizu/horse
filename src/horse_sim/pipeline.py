from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from horse_sim.ability.as_of import ability_as_of
from horse_sim.ability.rating import compute_raw_performances, iterative_adjust, par_seconds
from horse_sim.config import settings
from horse_sim.db.models import (
    Horse,
    ModelVersion,
    PredictionExplanation,
    Race,
    RaceEntry,
    SimulationResult,
)
from horse_sim.explain.reasons import build_explanations, confidence_label
from horse_sim.factors.engine import combined_expression, lookup_factors
from horse_sim.monte_carlo.simulate import HorseDrawInput, simulate
from horse_sim.normalize.pipeline import normalize_performances
from horse_sim.odds.compare import edge, expected_value, market_win_prob
from horse_sim.pace.scenarios import pace_prior_from_styles


@dataclass
class RacePrediction:
    race: Race
    pace: dict[str, float]
    horses: list[dict]


def ensure_model_version(session: Session) -> None:
    if session.query(ModelVersion).filter_by(code=settings.model_code).one_or_none() is None:
        session.add(
            ModelVersion(
                code=settings.model_code,
                description="Phase 1: タイム対パラ＋相手補正の基礎能力。条件係数は未推定のため1.0。",
            )
        )
        session.commit()


def fit_abilities(session: Session, as_of: date | None = None) -> None:
    normalize_performances(session)
    compute_raw_performances(session, as_of=as_of)
    iterative_adjust(session)
    ensure_model_version(session)


def predicted_time(ability: float, distance: int) -> float:
    par = par_seconds(distance)
    figure = ability
    # invert time_figure approximately
    per_600 = 600.0 / max(distance, 1)
    scale = settings.time_figure_scale
    return par - (figure - 100.0) / max(scale * per_600 * 5.0, 1e-6)


def predict_race(session: Session, race_id: int, draws: int | None = None) -> RacePrediction:
    race = session.get(Race, race_id)
    if race is None:
        raise KeyError(f"race {race_id} not found")
    as_of = race.date
    entries = session.query(RaceEntry).filter_by(race_id=race_id).all()
    if not entries:
        raise ValueError("no entries")

    pace = pace_prior_from_styles(entries)
    inputs: list[HorseDrawInput] = []
    meta: dict[int, dict] = {}
    styles: dict[int, str] = {}

    for entry in entries:
        horse = session.get(Horse, entry.horse_id)
        ab = ability_as_of(session, entry.horse_id, as_of)
        factors = lookup_factors(session, race, entry)
        expr = combined_expression(factors)
        inputs.append(
            HorseDrawInput(
                horse_id=entry.horse_id,
                base_ability=ab.base_ability,
                ability_sd=ab.ability_sd,
                expression_rate=expr,
            )
        )
        styles[entry.horse_id] = entry.running_style or ""
        meta[entry.horse_id] = {
            "horse": horse,
            "entry": entry,
            "ability": ab,
            "factors": factors,
            "expression": expr,
        }

    sim = simulate(inputs, pace, draws=draws, styles=styles)
    n_draw = sim.draws

    session.query(SimulationResult).filter_by(race_id=race_id, model_version=settings.model_code).delete()
    session.query(PredictionExplanation).filter_by(race_id=race_id).delete()

    horses_out: list[dict] = []
    for hid, m in meta.items():
        horse: Horse = m["horse"]
        entry: RaceEntry = m["entry"]
        ab = m["ability"]
        expr = m["expression"]
        pred_ab = ab.base_ability * expr
        t_pred = predicted_time(pred_ab, race.distance)
        mkt = market_win_prob(entry.odds)
        ev = expected_value(sim.p_win[hid], entry.odds)
        ed = edge(sim.p_win[hid], entry.odds)
        conf = confidence_label(ab.n_starts, ab.ability_sd)
        low = (ab.base_ability - 1.28 * ab.ability_sd) * (expr - 0.02)
        high = (ab.base_ability + 1.28 * ab.ability_sd) * (expr + 0.02)
        expl = build_explanations(horse.name, ab, m["factors"], expr)
        row = SimulationResult(
            race_id=race.id,
            horse_id=hid,
            model_version=settings.model_code,
            base_ability=ab.base_ability,
            ability_sd=ab.ability_sd,
            expression_rate=expr,
            predicted_ability=round(pred_ab, 3),
            predicted_time=round(t_pred, 2),
            p_win=sim.p_win[hid],
            p_second=sim.p_second[hid],
            p_third=sim.p_third[hid],
            p_show=sim.p_show[hid],
            mean_rank=sim.mean_rank[hid],
            ability_low=round(low, 3),
            ability_high=round(high, 3),
            expression_low=max(0.85, expr - 0.03),
            expression_high=min(1.08, expr + 0.03),
            confidence=conf,
            n_starts_used=ab.n_starts,
            market_win_prob=mkt,
            edge=ed,
            expected_value=ev,
            draws=n_draw,
        )
        session.add(row)
        for e in expl:
            session.add(
                PredictionExplanation(
                    race_id=race.id,
                    horse_id=hid,
                    kind=e["kind"],
                    factor_name=e["factor_name"],
                    magnitude=e["magnitude"],
                    sample_size=e["sample_size"],
                    confidence=e["confidence"],
                    text=e["text"],
                )
            )
        plus = [e["text"] for e in expl if e["kind"] == "plus"]
        minus = [e["text"] for e in expl if e["kind"] == "minus"]
        weak = [e["text"] for e in expl if e["kind"] == "weak"]
        method = [e["text"] for e in expl if e["kind"] == "method"]
        horses_out.append(
            {
                "horse_id": hid,
                "name": horse.name,
                "base_ability": ab.base_ability,
                "ability_sd": ab.ability_sd,
                "expression_rate": expr,
                "predicted_ability": round(pred_ab, 3),
                "predicted_time": round(t_pred, 2),
                "p_win": sim.p_win[hid],
                "p_second": sim.p_second[hid],
                "p_third": sim.p_third[hid],
                "p_show": sim.p_show[hid],
                "mean_rank": sim.mean_rank[hid],
                "ability_low": round(low, 3),
                "ability_high": round(high, 3),
                "expression_low": max(0.85, expr - 0.03),
                "expression_high": min(1.08, expr + 0.03),
                "confidence": conf,
                "n_starts": ab.n_starts,
                "odds": entry.odds,
                "market_win_prob": mkt,
                "edge": ed,
                "expected_value": ev,
                "plus": plus,
                "minus": minus,
                "weak": weak,
                "method": method,
                "gate": entry.gate,
                "style": entry.running_style,
            }
        )

    session.commit()
    horses_out.sort(key=lambda r: r["p_win"], reverse=True)
    best_ability = max(horses_out, key=lambda r: r["predicted_ability"])
    value_candidates = [h for h in horses_out if h["expected_value"] is not None]
    best_ev = max(value_candidates, key=lambda r: r["expected_value"]) if value_candidates else None
    for h in horses_out:
        h["mark_ability"] = h["horse_id"] == best_ability["horse_id"]
        h["mark_value"] = best_ev is not None and h["horse_id"] == best_ev["horse_id"]

    total_pace = sum(sim.pace_counts.values()) or 1
    pace_out = {k: sim.pace_counts[k] / total_pace for k in ("slow", "normal", "fast")}
    return RacePrediction(race=race, pace=pace_out, horses=horses_out)
