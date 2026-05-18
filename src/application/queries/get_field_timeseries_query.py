from dataclasses import dataclass


@dataclass(frozen=True)
class GetFieldTimeseriesQuery:
    field_id: str
    limit: int = 30
