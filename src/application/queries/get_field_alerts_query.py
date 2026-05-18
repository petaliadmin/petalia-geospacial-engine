from dataclasses import dataclass


@dataclass(frozen=True)
class GetFieldAlertsQuery:
    field_id: str
    limit: int = 50
    offset: int = 0
