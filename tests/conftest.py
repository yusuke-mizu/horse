import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from horse_sim.db.models import Base


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
