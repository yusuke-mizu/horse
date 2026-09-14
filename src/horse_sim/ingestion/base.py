from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class IngestReport:
    source: str
    fetched_at: datetime
    races: int
    entries: int
    missing_rate: float
    duplicate_rate: float
    quality_score: float
    notes: str = ""


class DataSourceAdapter(ABC):
    """無料・有料を問わず、取得元ごとの品質を必ず記録する。"""

    name: str

    @abstractmethod
    def load(self) -> dict[str, Any]:
        raise NotImplementedError
