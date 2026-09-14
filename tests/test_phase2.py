from datetime import date, timedelta

from horse_sim.db.models import Horse, HorsePerformance, Race, RaceEntry
from horse_sim.factors.aptitude import horse_condition_factors
from horse_sim.factors.estimate import build_population_index
from horse_sim.ingestion.synthetic import ingest_synthetic
from horse_sim.pipeline import fit_abilities, predict_race


def test_distance_curve_uses_own_record(session_factory):
    session = session_factory()
    horse = Horse(name="距離馬")
    session.add(horse)
    session.flush()
    as_of = date(2024, 6, 1)
    past = []
    for i in range(6):
        d = date(2024, 1, 1) + timedelta(days=i * 7)
        r = Race(date=d, course="東京", surface="turf", distance=1200, track_condition="良")
        session.add(r)
        session.flush()
        p = HorsePerformance(
            horse_id=horse.id,
            race_id=r.id,
            date=d,
            course="東京",
            surface="turf",
            distance=1200,
            track_condition="良",
            adjusted_performance=108.0,
        )
        session.add(p)
        past.append(p)
    for i in range(2):
        d = date(2024, 3, 1) + timedelta(days=i * 7)
        r = Race(date=d, course="東京", surface="turf", distance=2000, track_condition="良")
        session.add(r)
        session.flush()
        p = HorsePerformance(
            horse_id=horse.id,
            race_id=r.id,
            date=d,
            course="東京",
            surface="turf",
            distance=2000,
            track_condition="良",
            adjusted_performance=92.0,
        )
        session.add(p)
        past.append(p)
    today = Race(date=as_of, course="東京", surface="turf", distance=1200, track_condition="良")
    session.add(today)
    session.flush()
    entry = RaceEntry(race_id=today.id, horse_id=horse.id, gate=3)
    session.add(entry)
    session.commit()
    factors = horse_condition_factors(session, today, entry, as_of, past)
    dist = next(f for f in factors if f.factor_name == "horse_distance")
    assert dist.used
    assert dist.effect_size > 0


def test_population_excludes_race_day(session_factory):
    session = session_factory()
    horse = Horse(name="残差馬")
    session.add(horse)
    session.flush()
    r1 = Race(date=date(2024, 1, 1), course="京都", surface="turf", distance=1600, track_condition="良")
    r2 = Race(date=date(2024, 6, 1), course="京都", surface="turf", distance=1600, track_condition="不良")
    session.add_all([r1, r2])
    session.flush()
    session.add(
        HorsePerformance(
            horse_id=horse.id,
            race_id=r1.id,
            date=r1.date,
            course="京都",
            surface="turf",
            distance=1600,
            track_condition="良",
            adjusted_performance=100.0,
            estimated_ability=100.0,
            gate=1,
        )
    )
    session.add(
        HorsePerformance(
            horse_id=horse.id,
            race_id=r2.id,
            date=r2.date,
            course="京都",
            surface="turf",
            distance=1600,
            track_condition="不良",
            adjusted_performance=180.0,
            estimated_ability=180.0,
            gate=1,
        )
    )
    session.commit()
    index = build_population_index(session, r2.date)
    assert index.going_effect("turf", "不良") is None
    going = index.going_effect("turf", "良")
    assert going is not None
    assert going.sample_size == 1


def test_synthetic_gate_not_finish_order(session_factory):
    session = session_factory()
    ingest_synthetic(session, n_horses=24, n_race_days=6, races_per_day=2, seed=3)
    from horse_sim.db.models import RaceEntry, HorsePerformance

    mismatched = 0
    n = 0
    for e in session.query(RaceEntry).all():
        p = (
            session.query(HorsePerformance)
            .filter_by(race_id=e.race_id, horse_id=e.horse_id)
            .one_or_none()
        )
        if p and p.finish_position:
            n += 1
            if e.gate != p.finish_position:
                mismatched += 1
    assert n > 10
    assert mismatched > 0


def test_phase2_predict_keeps_expression_bounded(session_factory):
    session = session_factory()
    ingest_synthetic(session, n_horses=24, n_race_days=12, races_per_day=2, seed=2)
    fit_abilities(session)
    from horse_sim.db.models import Race

    race = session.query(Race).order_by(Race.date.desc()).first()
    pred = predict_race(session, race.id, draws=200, persist=False)
    assert all(0.90 <= h["expression_rate"] <= 1.10 for h in pred.horses)
    assert any("距離適性" in t or "馬場適性" in t or "コース適性" in t or "gate_band" in t for h in pred.horses for t in h["method"] + h["plus"] + h["minus"] + h["weak"])
