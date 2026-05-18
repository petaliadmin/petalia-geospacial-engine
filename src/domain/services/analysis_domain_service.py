from src.domain.entities.analysis import Analysis
from src.domain.entities.field import Field
from src.domain.value_objects.analysis_status import AnalysisStatus
from src.shared.exceptions import AnalysisAlreadyRunningException


class AnalysisDomainService:
    """Domain service for analysis lifecycle rules."""

    def validate_can_create_analysis(
        self,
        field: Field,
        running_analysis: Analysis | None,
    ) -> None:
        if running_analysis and running_analysis.status in (
            AnalysisStatus.PENDING,
            AnalysisStatus.RUNNING,
        ):
            raise AnalysisAlreadyRunningException(field.id)
