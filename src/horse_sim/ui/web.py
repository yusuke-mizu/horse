from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from horse_sim.db.models import Race, get_session_factory, init_db
from horse_sim.pipeline import fit_abilities, predict_race

TEMPLATES = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES))
app = FastAPI(title="競馬予想シミュレーション")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    session = get_session_factory()()
    races = session.query(Race).order_by(Race.date.desc(), Race.race_number.asc()).limit(80).all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"races": races},
    )


@app.get("/races/{race_id}", response_class=HTMLResponse)
def race_view(request: Request, race_id: int):
    session = get_session_factory()()
    race = session.get(Race, race_id)
    if race is None:
        raise HTTPException(404)
    fit_abilities(session)
    pred = predict_race(session, race_id)
    return templates.TemplateResponse(
        request=request,
        name="race.html",
        context={"pred": pred},
    )


@app.get("/api/races/{race_id}")
def race_api(race_id: int):
    session = get_session_factory()()
    if session.get(Race, race_id) is None:
        raise HTTPException(404)
    fit_abilities(session)
    pred = predict_race(session, race_id)
    return {
        "race_id": pred.race.id,
        "course": pred.race.course,
        "date": str(pred.race.date),
        "surface": pred.race.surface,
        "distance": pred.race.distance,
        "track_condition": pred.race.track_condition,
        "pace": pred.pace,
        "horses": pred.horses,
    }
