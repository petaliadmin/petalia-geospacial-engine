import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def mock_batch_deps():
    with (
        patch("src.infrastructure.workers.batch_analysis_worker.get_redis_sync") as mock_redis,
        patch("src.infrastructure.workers.analysis_worker.run_analysis") as mock_run,
        patch("src.infrastructure.workers.batch_analysis_worker.celery_app") as mock_app,
        patch("src.infrastructure.workers.batch_analysis_worker.logger") as mock_logger
    ):
        yield {
            "redis": mock_redis,
            "run": mock_run,
            "app": mock_app,
            "logger": mock_logger
        }

def test_on_batch_completed(mock_batch_deps):
    from src.infrastructure.workers.batch_analysis_worker import on_batch_completed
    
    mock_redis_client = MagicMock()
    mock_batch_deps["redis"].return_value = mock_redis_client
    
    # Simulate a mix of success and failure
    results = [
        {"analysis_id": "a1", "status": "COMPLETED"},
        {"analysis_id": "a2", "status": "COMPLETED"},
        {"analysis_id": "a3", "status": "FAILED", "error": "Task failed"}
    ]
    
    res = on_batch_completed(results, "batch-1")
    
    assert res["batch_id"] == "batch-1"
    assert res["submitted"] == 3
    assert res["succeeded"] == 2
    assert res["failed"] == 1
    
    # Check if redis was updated
    mock_redis_client.setex.assert_called_once()
    
def test_run_analysis_safe(mock_batch_deps):
    from src.infrastructure.workers.batch_analysis_worker import run_analysis_safe
    
    mock_batch_deps["run"].return_value = {"status": "COMPLETED"}
    
    res = run_analysis_safe(
        analysis_id="a1",
        field_id="f1",
        external_field_id="ef1",
        geometry={},
        requested_metrics=[],
        batch_id="b1"
    )
    
    assert res["status"] == "COMPLETED"
    
def test_run_analysis_safe_catches_error(mock_batch_deps):
    from src.infrastructure.workers.batch_analysis_worker import run_analysis_safe
    
    mock_batch_deps["run"].side_effect = RuntimeError("Failed")
    
    res = run_analysis_safe(
        analysis_id="a1",
        field_id="f1",
        external_field_id="ef1",
        geometry={},
        requested_metrics=[],
        batch_id="b1"
    )
    
    assert res["status"] == "FAILED"
    assert "Failed" in res["error"]
