
from src.domain.entities.analysis import Analysis
from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.requested_metrics import RequestedMetric


def test_analysis_create_pending():
    analysis = Analysis.create(
        field_id="field-uuid",
        requested_metrics=[RequestedMetric.NDVI, RequestedMetric.ALERTS],
    )
    assert analysis.status == AnalysisStatus.PENDING
    assert analysis.id.startswith("ana_")
    assert analysis.completed_at is None


def test_analysis_mark_running():
    analysis = Analysis.create(field_id="f1", requested_metrics=[RequestedMetric.NDVI])
    analysis.mark_running()
    assert analysis.status == AnalysisStatus.RUNNING


def test_analysis_mark_completed():
    analysis = Analysis.create(field_id="f1", requested_metrics=[RequestedMetric.NDVI])
    analysis.mark_running()
    analysis.mark_completed()
    assert analysis.status == AnalysisStatus.COMPLETED
    assert analysis.completed_at is not None
    assert analysis.is_terminal is True


def test_analysis_mark_failed():
    analysis = Analysis.create(field_id="f1", requested_metrics=[RequestedMetric.NDVI])
    analysis.mark_failed("GEE timeout")
    assert analysis.status == AnalysisStatus.FAILED
    assert analysis.error_message == "GEE timeout"
    assert analysis.is_terminal is True


def test_analysis_is_not_terminal_when_pending():
    analysis = Analysis.create(field_id="f1", requested_metrics=[RequestedMetric.NDVI])
    assert analysis.is_terminal is False
