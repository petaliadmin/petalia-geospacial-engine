from dataclasses import dataclass


@dataclass(frozen=True)
class GetAnalysisQuery:
    analysis_id: str
