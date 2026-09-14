from __future__ import annotations

from dataclasses import dataclass, field
from random import Random

from horse_sim.config import settings
from horse_sim.pace.scenarios import PacePrior


@dataclass
class HorseDrawInput:
    horse_id: int
    base_ability: float
    ability_sd: float
    expression_rate: float
    expression_sd: float = 0.012


@dataclass
class SimOutput:
    draws: int
    p_win: dict[int, float]
    p_second: dict[int, float]
    p_third: dict[int, float]
    p_show: dict[int, float]
    mean_rank: dict[int, float]
    mean_perf: dict[int, float]
    pace_counts: dict[str, int] = field(default_factory=dict)


def simulate(
    horses: list[HorseDrawInput],
    pace: PacePrior,
    *,
    draws: int | None = None,
    seed: int = 7,
    styles: dict[int, str] | None = None,
    pace_style_shifts: dict[str, dict[str, float]] | None = None,
) -> SimOutput:
    draws = draws or settings.monte_carlo_draws
    rng = Random(seed)
    ids = [h.horse_id for h in horses]
    win = {i: 0 for i in ids}
    second = {i: 0 for i in ids}
    third = {i: 0 for i in ids}
    rank_sum = {i: 0.0 for i in ids}
    perf_sum = {i: 0.0 for i in ids}
    pace_counts = {"slow": 0, "normal": 0, "fast": 0}
    pairs = pace.as_pairs()
    styles = styles or {}

    for _ in range(draws):
        u = rng.random()
        acc = 0.0
        label = "normal"
        for name, p in pairs:
            acc += p
            if u <= acc:
                label = name
                break
        pace_counts[label] += 1
        shifts = (pace_style_shifts or {}).get(label, {})
        samples: list[tuple[int, float]] = []
        for h in horses:
            expr = rng.gauss(h.expression_rate, h.expression_sd)
            ability = rng.gauss(h.base_ability, h.ability_sd)
            noise = rng.gauss(0.0, settings.performance_noise)
            style = styles.get(h.horse_id, "")
            shift = shifts.get(style, 0.0)
            perf = ability * expr + noise + shift
            samples.append((h.horse_id, perf))
            perf_sum[h.horse_id] += perf
        samples.sort(key=lambda x: x[1], reverse=True)
        for rank, (hid, _) in enumerate(samples, start=1):
            rank_sum[hid] += rank
            if rank == 1:
                win[hid] += 1
            elif rank == 2:
                second[hid] += 1
            elif rank == 3:
                third[hid] += 1

    n = float(draws)
    show = {i: (win[i] + second[i] + third[i]) / n for i in ids}
    return SimOutput(
        draws=draws,
        p_win={i: win[i] / n for i in ids},
        p_second={i: second[i] / n for i in ids},
        p_third={i: third[i] / n for i in ids},
        p_show=show,
        mean_rank={i: rank_sum[i] / n for i in ids},
        mean_perf={i: perf_sum[i] / n for i in ids},
        pace_counts=pace_counts,
    )
