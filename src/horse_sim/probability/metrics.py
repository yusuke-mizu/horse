from __future__ import annotations

import math


def brier_win(probs: list[float], outcomes: list[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / max(len(probs), 1)


def log_loss_win(probs: list[float], outcomes: list[int]) -> float:
    eps = 1e-12
    return -sum(y * math.log(max(min(p, 1 - eps), eps)) + (1 - y) * math.log(max(min(1 - p, 1 - eps), eps)) for p, y in zip(probs, outcomes)) / max(len(probs), 1)


def calibration_bins(probs: list[float], outcomes: list[int], n_bins: int = 10) -> list[dict]:
    bins = [{"p": 0.0, "y": 0.0, "n": 0} for _ in range(n_bins)]
    for p, y in zip(probs, outcomes):
        idx = min(n_bins - 1, int(p * n_bins))
        bins[idx]["p"] += p
        bins[idx]["y"] += y
        bins[idx]["n"] += 1
    out = []
    for i, b in enumerate(bins):
        if b["n"] == 0:
            continue
        out.append(
            {
                "bin": i,
                "mean_pred": b["p"] / b["n"],
                "mean_actual": b["y"] / b["n"],
                "n": b["n"],
            }
        )
    return out
