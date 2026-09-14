from __future__ import annotations

from pathlib import Path

import typer
from sqlalchemy.orm import Session

from horse_sim.config import settings
from horse_sim.db.models import Race, get_session_factory, init_db
from horse_sim.ingestion.csv_loader import ingest_csv
from horse_sim.ingestion.synthetic import ingest_synthetic
from horse_sim.pipeline import fit_abilities, predict_race

app = typer.Typer(help="競馬予想シミュレーション CLI")


def _session() -> Session:
    init_db()
    return get_session_factory()()


@app.command()
def init() -> None:
    init_db()
    typer.echo(f"initialized {settings.database_url}")


@app.command("ingest-synthetic")
def ingest_synthetic_cmd(seed: int = 42) -> None:
    session = _session()
    report = ingest_synthetic(session, seed=seed)
    typer.echo(
        f"{report.source}: races={report.races} entries={report.entries} quality={report.quality_score:.2f}"
    )


@app.command("ingest-csv")
def ingest_csv_cmd(
    races: Path = typer.Option(..., exists=True),
    entries: Path = typer.Option(..., exists=True),
    source: str = "csv",
) -> None:
    session = _session()
    report = ingest_csv(session, races, entries, source=source)
    typer.echo(
        f"{report.source}: races={report.races} entries={report.entries} missing={report.missing_rate:.3f}"
    )


@app.command()
def rate() -> None:
    session = _session()
    fit_abilities(session)
    typer.echo("ability ratings updated (time-ordered, no future par times)")


@app.command()
def predict(race_id: int, draws: int = 2000) -> None:
    session = _session()
    pred = predict_race(session, race_id, draws=draws)
    r = pred.race
    typer.echo(f"{r.course} {r.race_name or r.id} {r.surface} {r.distance}m {r.track_condition}")
    typer.echo(
        f"展開 スロー {pred.pace['slow']:.0%} 平均 {pred.pace['normal']:.0%} ハイ {pred.pace['fast']:.0%}"
    )
    typer.echo(
        f"{'馬名':<16} {'基礎':>6} {'発揮':>7} {'予測':>6} {'1着':>7} {'3着内':>7} {'信頼':>4} 印"
    )
    for h in pred.horses:
        marks = ""
        if h["mark_ability"]:
            marks += "◎"
        if h["mark_value"]:
            marks += "★"
        typer.echo(
            f"{h['name']:<16} {h['base_ability']:6.1f} {h['expression_rate']*100:6.1f}% "
            f"{h['predicted_ability']:6.1f} {h['p_win']*100:6.1f}% {h['p_show']*100:6.1f}% "
            f"{h['confidence']:>4} {marks}"
        )


@app.command()
def races(limit: int = 20) -> None:
    session = _session()
    rows = session.query(Race).order_by(Race.date.desc()).limit(limit).all()
    for r in rows:
        typer.echo(f"{r.id}\t{r.date}\t{r.course}\t{r.race_name}\t{r.surface}\t{r.distance}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run("horse_sim.ui.web:app", host=host, port=port, reload=False)


@app.command()
def backtest(start: str = "2023-01-01", draws: int = 400) -> None:
    from datetime import date

    from horse_sim.backtest.split import summarize_win_probs
    from horse_sim.db.models import HorsePerformance

    session = _session()
    fit_abilities(session)
    start_d = date.fromisoformat(start)
    rows = session.query(Race).filter(Race.date >= start_d).order_by(Race.date.asc()).limit(30).all()
    probs: list[float] = []
    wins: list[int] = []
    for race in rows:
        pred = predict_race(session, race.id, draws=draws)
        for h in pred.horses:
            actual = (
                session.query(HorsePerformance)
                .filter_by(race_id=race.id, horse_id=h["horse_id"])
                .one_or_none()
            )
            if actual is None or actual.finish_position is None:
                continue
            probs.append(h["p_win"])
            wins.append(1 if actual.finish_position == 1 else 0)
    summary = summarize_win_probs(probs, wins)
    typer.echo(f"n={summary['n']} brier={summary['brier']:.4f} log_loss={summary['log_loss']:.4f}")


if __name__ == "__main__":
    app()
