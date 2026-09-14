from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from horse_sim.db.models import FactorEffect
from horse_sim.factors.context import gate_band
from horse_sim.factors.residuals import collect_residuals
from horse_sim.factors.stats import EffectEstimate, from_residuals


PHASE2_VERSION = "ability_v2"


@dataclass
class PopulationIndex:
    estimates: list[EffectEstimate]
    gate: dict[tuple, EffectEstimate]
    going: dict[tuple, EffectEstimate]
    style_pace: dict[tuple[str, str], EffectEstimate]

    def gate_effect(self, course: str, surface: str, band: str | None) -> EffectEstimate | None:
        if not band:
            return None
        for key in (
            ("gate_band", course, surface, band),
            ("gate_band", surface, band),
            ("gate_band", band),
        ):
            if key in self.gate:
                return self.gate[key]
        return None

    def going_effect(self, surface: str, going: str | None) -> EffectEstimate | None:
        if not going:
            return None
        for key in (("going", surface, going), ("going", going)):
            if key in self.going:
                return self.going[key]
        return None

    def style_pace_shift(self, style: str | None, pace: str) -> float:
        if not style:
            return 0.0
        est = self.style_pace.get((style, pace))
        if est is None:
            return 0.0
        from horse_sim.factors.stats import confidence_cap

        cap = confidence_cap(est.sample_size, est.confidence)
        strength = cap * (est.reproducibility or 0.5)
        return est.effect_size * 100.0 * strength


def build_population_index(session: Session, as_of: date) -> PopulationIndex:
    rows = collect_residuals(session, as_of)
    estimates: list[EffectEstimate] = []
    gate_map: dict[tuple, EffectEstimate] = {}
    going_map: dict[tuple, EffectEstimate] = {}
    sp_map: dict[tuple[str, str], EffectEstimate] = {}

    def add(est: EffectEstimate, store: dict, key: tuple) -> None:
        estimates.append(est)
        store[key] = est

    # going (surface × condition, then condition)
    by_going: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        if r.going:
            by_going[(r.surface, r.going)].append(r.residual)
            by_going[(r.going,)].append(r.residual)
    for key, vals in by_going.items():
        if len(key) == 2:
            cond = {"surface": key[0], "track_condition": key[1]}
            est = from_residuals("going", cond, vals)
            add(est, going_map, ("going", key[0], key[1]))
        else:
            cond = {"track_condition": key[0]}
            est = from_residuals("going", cond, vals)
            add(est, going_map, ("going", key[0]))

    # gate hierarchy
    by_gate: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        band = gate_band(r.gate)
        if not band:
            continue
        by_gate[(r.course, r.surface, band)].append(r.residual)
        by_gate[(r.surface, band)].append(r.residual)
        by_gate[(band,)].append(r.residual)
    for key, vals in by_gate.items():
        if len(key) == 3:
            cond = {"course": key[0], "surface": key[1], "gate_band": key[2]}
            est = from_residuals("gate_band", cond, vals)
            add(est, gate_map, ("gate_band", key[0], key[1], key[2]))
        elif len(key) == 2:
            cond = {"surface": key[0], "gate_band": key[1]}
            est = from_residuals("gate_band", cond, vals)
            add(est, gate_map, ("gate_band", key[0], key[1]))
        else:
            cond = {"gate_band": key[0]}
            est = from_residuals("gate_band", cond, vals)
            add(est, gate_map, ("gate_band", key[0]))

    by_sp: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        if r.style and r.pace:
            by_sp[(r.style, r.pace)].append(r.residual)
    for (style, pace), vals in by_sp.items():
        est = from_residuals(
            "style_pace",
            {"running_style": style, "pace_label": pace},
            vals,
            notes="展開シナリオごとに Monte Carlo で適用。発揮率の固定乗数にはしない。",
        )
        estimates.append(est)
        sp_map[(style, pace)] = est

    return PopulationIndex(estimates=estimates, gate=gate_map, going=going_map, style_pace=sp_map)


def persist_population(session: Session, index: PopulationIndex, as_of: date) -> int:
    session.query(FactorEffect).filter(FactorEffect.model_version == PHASE2_VERSION).delete()
    n = 0
    train_end = as_of
    for est in index.estimates:
        session.add(
            FactorEffect(
                factor_name=est.factor_name,
                effect_direction=est.direction,
                effect_size=est.effect_size,
                sample_size=est.sample_size,
                confidence=est.confidence,
                conditions=json.dumps(est.conditions, ensure_ascii=False),
                performance_change=est.mean_residual,
                statistical_significance=est.statistical_significance,
                reproducibility=est.reproducibility,
                train_end=train_end,
                model_version=PHASE2_VERSION,
                notes=est.notes,
            )
        )
        n += 1
    session.commit()
    return n


def pace_style_matrix(index: PopulationIndex) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {"slow": {}, "normal": {}, "fast": {}}
    for (style, pace), est in index.style_pace.items():
        if pace not in out:
            continue
        out[pace][style] = index.style_pace_shift(style, pace)
    return out
