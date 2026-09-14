from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from horse_sim.config import settings
from horse_sim.db.models import HorsePerformance, Race, RaceResult


def par_seconds(distance: int) -> float:
    """距離の粗い基準時計。コース別パラはデータから上書きする。"""
    return distance / 16.4


def build_par_table(session: Session, as_of: date) -> dict[tuple[str, str, int, str | None], float]:
    """as_of より前の勝ち時計中央値。サンプル不足のキーは使わない。"""
    buckets: dict[tuple[str, str, int, str | None], list[float]] = defaultdict(list)
    q = (
        session.query(Race, RaceResult)
        .join(RaceResult, RaceResult.race_id == Race.id)
        .filter(Race.date < as_of, RaceResult.winning_time.isnot(None))
    )
    for race, result in q:
        if result.winning_time and result.winning_time > 0:
            buckets[(race.course, race.surface, race.distance, race.track_condition)].append(
                result.winning_time
            )
    pars: dict[tuple[str, str, int, str | None], float] = {}
    for key, times in buckets.items():
        if len(times) < 5:
            continue
        ordered = sorted(times)
        pars[key] = ordered[len(ordered) // 2]
    return pars


def time_figure(finish_time: float, par: float, distance: int, scale: float | None = None) -> float:
    scale = scale if scale is not None else settings.time_figure_scale
    if finish_time <= 0 or par <= 0:
        return settings.ability_prior
    per_600 = 600.0 / max(distance, 1)
    return 100.0 + (par - finish_time) * scale * per_600 * 5.0


def compute_raw_performances(session: Session, as_of: date | None = None) -> int:
    """着順ではなく走破タイム対パラで raw_performance を付ける。パラは当該走より前の勝ち時計のみ。"""
    from statistics import median

    updated = 0
    max_as_of = as_of or date.max
    perfs = (
        session.query(HorsePerformance)
        .filter(HorsePerformance.date < max_as_of)
        .order_by(HorsePerformance.date.asc(), HorsePerformance.race_id.asc())
        .all()
    )
    winners: dict[int, float] = {}
    for race, result in (
        session.query(Race, RaceResult)
        .join(RaceResult, RaceResult.race_id == Race.id)
        .filter(Race.date < max_as_of, RaceResult.winning_time.isnot(None))
    ):
        winners[race.id] = result.winning_time

    history: dict[tuple[str, str, int, str | None], list[float]] = defaultdict(list)
    pending_keys: list[tuple[tuple[str, str, int, str | None], float]] = []

    def flush_pending():
        for key, wt in pending_keys:
            history[key].append(wt)
        pending_keys.clear()

    current_race_id = None
    for perf in perfs:
        if perf.finish_time is None:
            continue
        if current_race_id != perf.race_id:
            flush_pending()
            current_race_id = perf.race_id
            if winners.get(perf.race_id):
                pending_keys.append(
                    ((perf.course, perf.surface, perf.distance, perf.track_condition), winners[perf.race_id])
                )
        key = (perf.course, perf.surface, perf.distance, perf.track_condition)
        series = history.get(key) or []
        par = median(series) if len(series) >= 5 else par_seconds(perf.distance)
        perf.raw_performance = round(time_figure(perf.finish_time, par, perf.distance), 3)
        updated += 1
    session.commit()
    return updated


def iterative_adjust(session: Session) -> None:
    """相手レベルの反復補正。各走の estimated_ability は当該走以前のみで更新する。"""
    horses_ability: dict[int, float] = defaultdict(lambda: settings.ability_prior)
    horses_n: dict[int, int] = defaultdict(int)
    perfs = (
        session.query(HorsePerformance)
        .filter(HorsePerformance.raw_performance.isnot(None))
        .order_by(HorsePerformance.date.asc(), HorsePerformance.race_id.asc())
        .all()
    )
    by_race: dict[int, list[HorsePerformance]] = defaultdict(list)
    for p in perfs:
        by_race[p.race_id].append(p)

    for race_id in sorted(by_race, key=lambda rid: by_race[rid][0].date):
        field = by_race[race_id]
        pre_ability = {p.horse_id: horses_ability[p.horse_id] for p in field}
        field_mean = sum(pre_ability.values()) / max(len(pre_ability), 1)
        for p in field:
            raw = p.raw_performance or settings.ability_prior
            adj = raw + 0.45 * (field_mean - settings.ability_prior)
            p.adjusted_performance = round(adj, 3)
            n = horses_n[p.horse_id]
            k = settings.ability_prior_strength
            if n == 0:
                new_ab = (1.0 / (1.0 + k)) * adj + (k / (1.0 + k)) * settings.ability_prior
            else:
                decay = 0.78
                new_ab = decay * horses_ability[p.horse_id] + (1.0 - decay) * adj
            horses_ability[p.horse_id] = new_ab
            horses_n[p.horse_id] = n + 1
            p.estimated_ability = round(new_ab, 3)
    session.commit()
