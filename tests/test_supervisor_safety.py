from upsc_studio.agents.supervisor import ExecutiveProducer


def test_supervisor_does_not_retry_permanent_errors():
    calls = {"count": 0}

    def fail():
        calls["count"] += 1
        raise ValueError("invalid project input")

    result, output = ExecutiveProducer.run_with_retry(
        "AGENT_TEST", fail, [], max_retries=3, retry_safe=True
    )
    assert result.status == "FAILED"
    assert result.retry_count == 0
    assert output is None
    assert calls["count"] == 1


def test_supervisor_does_not_retry_side_effecting_task_by_default():
    calls = {"count": 0}

    def timeout():
        calls["count"] += 1
        raise TimeoutError("uncertain external operation")

    result, output = ExecutiveProducer.run_with_retry(
        "AGENT_TEST", timeout, [], max_retries=3
    )
    assert result.status == "FAILED"
    assert result.retry_count == 0
    assert output is None
    assert calls["count"] == 1


def test_supervisor_retries_only_opted_in_transient_failures():
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] == 1:
            raise ConnectionError("temporary connection issue")
        return {"ok": True}

    result, output = ExecutiveProducer.run_with_retry(
        "AGENT_TEST", flaky, [], max_retries=2, retry_safe=True
    )
    assert result.status == "COMPLETED"
    assert result.retry_count == 1
    assert output == {"ok": True}
    assert calls["count"] == 2
