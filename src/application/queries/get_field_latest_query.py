from dataclasses import dataclass


@dataclass(frozen=True)
class GetFieldLatestQuery:
    field_id: str
