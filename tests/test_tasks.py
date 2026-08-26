from common.tasks import TaskStatus, health_ping
from config import celery_app


def test_task_status_contract_is_stable():
    assert TaskStatus.QUEUED.value == "queued"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.COMPLETED.value == "completed"


def test_worker_health_task_executes_eagerly():
    result = health_ping.delay()

    assert result.get() == "pong"


def test_diagnostic_task_module_is_registered_for_real_workers():
    celery_app.loader.import_default_modules()

    assert "analyses.execute_diagnostic_run" in celery_app.tasks
