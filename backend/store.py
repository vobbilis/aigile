import uuid
from datetime import datetime, timezone

from models import MetricIn, MetricOut


class MetricStore:
    def __init__(self) -> None:
        self._data: list[MetricOut] = []

    def add(self, metric: MetricIn) -> MetricOut:
        out = MetricOut(
            id=str(uuid.uuid4()),
            name=metric.name,
            value=metric.value,
            tags=metric.tags,
            timestamp=datetime.now(timezone.utc),
        )
        self._data.append(out)
        return out

    def all(self) -> list[MetricOut]:
        return list(self._data)

    def by_name(self, name: str) -> list[MetricOut]:
        return [m for m in self._data if m.name == name]

    def delete(self, name: str) -> int:
        before = len(self._data)
        self._data = [m for m in self._data if m.name != name]
        return before - len(self._data)

    def clear(self) -> None:
        self._data = []
