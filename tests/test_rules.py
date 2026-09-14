from datetime import date

from horse_sim.db.models import FactorEffect, Horse, Race, RaceEntry
from horse_sim.factors.engine import lookup_factors
from horse_sim.normalize.pipeline import assert_no_future_leak
from horse_sim.odds.compare import edge, expected_value
from horse_sim.probability.metrics import brier_win


def test_no_future_leak_ok():
    assert_no_future_leak(date(2024, 6, 1), [date(2024, 5, 1)])


def test_no_future_leak_raises():
    try:
        assert_no_future_leak(date(2024, 6, 1), [date(2024, 6, 1)])
    except ValueError:
        return
    raise AssertionError("expected leak")


def test_small_sample_factor_not_applied(session_factory):
    session = session_factory()
    horse = Horse(name="X")
    session.add(horse)
    session.flush()
    race = Race(date=date(2024, 1, 1), course="京都", surface="turf", distance=1600)
    session.add(race)
    session.flush()
    entry = RaceEntry(race_id=race.id, horse_id=horse.id)
    session.add(entry)
    session.add(
        FactorEffect(
            factor_name="first_blinkers",
            effect_size=0.048,
            sample_size=8,
            confidence=0.9,
            reproducibility=0.9,
            conditions="{}",
        )
    )
    session.commit()
    applied = lookup_factors(session, race, entry)
    assert applied[0].used is False
    assert abs(applied[0].multiplier - 1.0) < 1e-9


def test_odds_not_used_as_ability():
    assert expected_value(0.25, 6.0) == 1.5
    assert abs(edge(0.28, 1 / 0.18) - (0.28 - 0.18)) < 1e-9


def test_brier():
    assert abs(brier_win([0.5], [1]) - 0.25) < 1e-9
