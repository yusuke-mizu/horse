from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from horse_sim.config import settings


class Base(DeclarativeBase):
    pass


class Horse(Base):
    __tablename__ = "horses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    sex: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sire: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    damsire: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    dam_line: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    entries: Mapped[list["RaceEntry"]] = relationship(back_populates="horse")
    performances: Mapped[list["HorsePerformance"]] = relationship(back_populates="horse")


class Jockey(Base):
    __tablename__ = "jockeys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class Trainer(Base):
    __tablename__ = "trainers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class Pedigree(Base):
    __tablename__ = "pedigrees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"), unique=True)
    sire: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    dam: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    damsire: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    sire_line: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    dam_line: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)


class Race(Base):
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    course: Mapped[str] = mapped_column(String(40), index=True)
    surface: Mapped[str] = mapped_column(String(16))  # turf / dirt
    distance: Mapped[int] = mapped_column(Integer)
    track_condition: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    weather: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    race_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    race_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    class_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    going_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="unknown")
    source_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    entries: Mapped[list["RaceEntry"]] = relationship(back_populates="race")
    result: Mapped[Optional["RaceResult"]] = relationship(back_populates="race", uselist=False)


class RaceEntry(Base):
    __tablename__ = "race_entries"
    __table_args__ = (UniqueConstraint("race_id", "horse_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"), index=True)
    jockey_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jockeys.id"), nullable=True)
    trainer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("trainers.id"), nullable=True)
    gate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    draw: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    body_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    body_weight_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    odds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    popularity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    equipment: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    running_style: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    race: Mapped[Race] = relationship(back_populates="entries")
    horse: Mapped[Horse] = relationship(back_populates="entries")


class RaceResult(Base):
    __tablename__ = "race_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), unique=True)
    winning_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pace_first_half: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pace_second_half: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pace_label: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    race: Mapped[Race] = relationship(back_populates="result")


class HorsePerformance(Base):
    __tablename__ = "horse_performances"
    __table_args__ = (UniqueConstraint("horse_id", "race_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"), index=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    course: Mapped[str] = mapped_column(String(40))
    surface: Mapped[str] = mapped_column(String(16))
    distance: Mapped[int] = mapped_column(Integer)
    track_condition: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    weather: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    gate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    body_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    body_weight_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    jockey: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    pace: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    finish_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    finish_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_3f: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    margin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    class_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    raw_performance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    adjusted_performance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_ability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    horse: Mapped[Horse] = relationship(back_populates="performances")
    race: Mapped[Race] = relationship()


class TrackCondition(Base):
    __tablename__ = "track_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), unique=True)
    moisture: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cushion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    going_diff: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    clock_ease: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class TrackBias(Base):
    __tablename__ = "track_bias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    course: Mapped[str] = mapped_column(String(40))
    surface: Mapped[str] = mapped_column(String(16))
    race_from: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    race_to: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inside: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    outside: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    front: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    closer: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hierarchy: Mapped[str] = mapped_column(String(32), default="meeting")


class EquipmentChange(Base):
    __tablename__ = "equipment_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"))
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"))
    change_type: Mapped[str] = mapped_column(String(40))
    detail: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)


class OddsSnapshot(Base):
    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"))
    win_odds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_final: Mapped[int] = mapped_column(Integer, default=0)


class FactorEffect(Base):
    __tablename__ = "factor_effects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factor_name: Mapped[str] = mapped_column(String(80), index=True)
    effect_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    effect_size: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    conditions: Mapped[str] = mapped_column(Text, default="{}")
    historical_roi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    performance_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    statistical_significance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reproducibility: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    train_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    train_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    model_version: Mapped[str] = mapped_column(String(40), default="unestimated")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"))
    model_version: Mapped[str] = mapped_column(String(40))
    base_ability: Mapped[float] = mapped_column(Float)
    ability_sd: Mapped[float] = mapped_column(Float)
    expression_rate: Mapped[float] = mapped_column(Float)
    predicted_ability: Mapped[float] = mapped_column(Float)
    predicted_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p_win: Mapped[float] = mapped_column(Float)
    p_second: Mapped[float] = mapped_column(Float)
    p_third: Mapped[float] = mapped_column(Float)
    p_show: Mapped[float] = mapped_column(Float)
    mean_rank: Mapped[float] = mapped_column(Float)
    ability_low: Mapped[float] = mapped_column(Float)
    ability_high: Mapped[float] = mapped_column(Float)
    expression_low: Mapped[float] = mapped_column(Float)
    expression_high: Mapped[float] = mapped_column(Float)
    confidence: Mapped[str] = mapped_column(String(16))
    n_starts_used: Mapped[int] = mapped_column(Integer, default=0)
    market_win_prob: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    edge: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    draws: Mapped[int] = mapped_column(Integer)


class PredictionExplanation(Base):
    __tablename__ = "prediction_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"))
    kind: Mapped[str] = mapped_column(String(24))  # plus / minus / weak / method
    factor_name: Mapped[str] = mapped_column(String(80))
    magnitude: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    text: Mapped[str] = mapped_column(Text)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    parent_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    hit_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recovery_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    log_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brier: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calibration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ev_accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class OutcomeAnalysis(Base):
    __tablename__ = "outcome_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"))
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"))
    predicted_p_win: Mapped[float] = mapped_column(Float)
    actual_finish: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text)


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    missing_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duplicate_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trust: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, connect_args=connect_args)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


def init_db() -> None:
    Base.metadata.create_all(get_engine())
