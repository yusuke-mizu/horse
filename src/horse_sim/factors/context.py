from __future__ import annotations

from horse_sim.db.models import RaceEntry


def gate_band(gate: int | None) -> str | None:
    if gate is None:
        return None
    if gate <= 4:
        return "inner"
    if gate <= 8:
        return "mid"
    return "outer"


def normalize_pace(label: str | None) -> str | None:
    if not label:
        return None
    raw = label.strip().lower()
    mapping = {
        "slow": "slow",
        "スロー": "slow",
        "normal": "normal",
        "平均": "normal",
        "fast": "fast",
        "ハイ": "fast",
        "ハイペース": "fast",
    }
    return mapping.get(raw, mapping.get(label.strip(), None))


def pace_jp(label: str) -> str:
    return {"slow": "スロー", "normal": "平均", "fast": "ハイ"}.get(label, label)
