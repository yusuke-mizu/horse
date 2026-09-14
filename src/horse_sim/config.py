from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HORSE_SIM_")

    data_dir: Path = Path("data")
    database_url: str = "sqlite:///data/horse_sim.db"
    model_code: str = "ability_v1"
    monte_carlo_draws: int = 2000
    ability_prior: float = 100.0
    ability_prior_strength: float = 4.0
    time_figure_scale: float = 2.0
    performance_noise: float = 1.4

    @property
    def db_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.replace("sqlite:///", "", 1))
        return self.data_dir / "horse_sim.db"


settings = Settings()
