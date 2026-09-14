from datetime import date

from horse_sim.ability.as_of import ability_as_of
from horse_sim.db.models import Horse, HorsePerformance, Race
from horse_sim.ingestion.synthetic import ingest_synthetic
from horse_sim.pipeline import fit_abilities, predict_race


def test_synthetic_pipeline(session_factory):
    session = session_factory()
    ingest_synthetic(session, n_horses=24, n_race_days=12, races_per_day=2, seed=1)
    fit_abilities(session)
    race = session.query(Race).order_by(Race.date.desc()).first()
    pred = predict_race(session, race.id, draws=300)
    assert len(pred.horses) >= 2
    assert abs(sum(h["p_win"] for h in pred.horses) - 1.0) < 0.08
    assert all(0.90 <= h["expression_rate"] <= 1.10 for h in pred.horses)
    top = pred.horses[0]
    assert top["confidence"] in ("高", "中", "低")
    assert top["method"]


def test_ability_excludes_race_day(session_factory):
    session = session_factory()
    h = Horse(name="Y")
    session.add(h)
    session.flush()
    r1 = Race(date=date(2024, 1, 1), course="東京", surface="turf", distance=1600)
    r2 = Race(date=date(2024, 2, 1), course="東京", surface="turf", distance=1600)
    session.add_all([r1, r2])
    session.flush()
    session.add(
        HorsePerformance(
            horse_id=h.id,
            race_id=r1.id,
            date=r1.date,
            course="東京",
            surface="turf",
            distance=1600,
            finish_time=95.0,
            adjusted_performance=110.0,
        )
    )
    session.add(
        HorsePerformance(
            horse_id=h.id,
            race_id=r2.id,
            date=r2.date,
            course="東京",
            surface="turf",
            distance=1600,
            finish_time=94.0,
            adjusted_performance=200.0,
        )
    )
    session.commit()
    ab = ability_as_of(session, h.id, r2.date)
    assert ab.n_starts == 1
    assert ab.base_ability < 150
