from __future__ import annotations


TAKEOUT = 0.20  # 単勝の粗い控除。実控除は券種・開催で異なるため固定の真実ではない。


def market_win_prob(odds: float | None) -> float | None:
    if odds is None or odds <= 1.0:
        return None
    return 1.0 / odds


def expected_value(model_p: float, odds: float | None) -> float | None:
    if odds is None or odds <= 1.0:
        return None
    return model_p * odds


def edge(model_p: float, odds: float | None) -> float | None:
    m = market_win_prob(odds)
    if m is None:
        return None
    return model_p - m
