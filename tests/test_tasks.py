from common.tasks import TaskStatus, health_ping


def test_task_status_contract_is_stable():
    assert TaskStatus.QUEUED.value == "queued"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.COMPLETED.value == "completed"


def test_worker_health_task_executes_eagerly():
    result = health_ping.delay()

    assert result.get() == "pong"
