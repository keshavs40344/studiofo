import sqlite3

import pytest

from upsc_studio.agents.runtime import AgentTaskStore, DependencyScheduler, TaskSpec


def make_runtime():
    conn = sqlite3.connect(":memory:")
    store = AgentTaskStore(conn)
    return conn, store


def test_dag_runs_in_dependency_order_and_persists_outputs():
    _, store = make_runtime()
    seen = []
    scheduler = DependencyScheduler(store, {
        "first": lambda p: seen.append("first") or {"value": 7},
        "second": lambda p: seen.append("second") or {"value": p["n"]},
    })
    result = scheduler.run("wf-1", [
        TaskSpec("a", "AGENT_A", "first"),
        TaskSpec("b", "AGENT_B", "second", ("a",), {"n": 9}),
    ])
    assert result["status"] == "COMPLETED"
    assert seen == ["first", "second"]
    assert result["completed"] == 2
    assert result["tasks"][1]["output_json"] == '{"value": 9}'


def test_enqueue_is_idempotent_for_same_workflow_and_inputs():
    _, store = make_runtime()
    spec = TaskSpec("a", "AGENT_A", "noop", payload={"x": 1})
    first = store.enqueue("wf", spec, "hash")
    second = store.enqueue("wf", spec, "hash")
    assert first == second
    assert len(store.list_workflow("wf")) == 1


def test_cycle_and_missing_dependency_are_rejected():
    _, store = make_runtime()
    scheduler = DependencyScheduler(store, {})
    with pytest.raises(ValueError, match="cycle"):
        scheduler.validate([TaskSpec("a", "A", "x", ("b",)), TaskSpec("b", "B", "x", ("a",))])
    with pytest.raises(ValueError, match="unknown dependencies"):
        scheduler.validate([TaskSpec("a", "A", "x", ("missing",))])


def test_permanent_failure_blocks_downstream_task():
    _, store = make_runtime()
    scheduler = DependencyScheduler(store, {
        "bad": lambda p: (_ for _ in ()).throw(ValueError("bad input")),
        "next": lambda p: {"ok": True},
    })
    result = scheduler.run("wf-fail", [
        TaskSpec("a", "A", "bad"),
        TaskSpec("b", "B", "next", ("a",)),
    ])
    assert result["status"] == "FAILED"
    assert result["failed"] == 1
    assert result["blocked"] == 1


def test_transient_failure_retries_with_bounded_attempts():
    _, store = make_runtime()
    calls = {"n": 0}
    def flaky(_):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("temporary")
        return {"ok": True}
    result = DependencyScheduler(store, {"flaky": flaky}).run(
        "wf-retry", [TaskSpec("a", "A", "flaky", max_retries=2)]
    )
    assert result["status"] == "COMPLETED"
    assert calls["n"] == 2


def test_checkpoint_round_trip_and_event_log():
    _, store = make_runtime()
    store.checkpoint("wf", "research", {"source_count": 3})
    assert store.read_checkpoint("wf", "research") == {"source_count": 3}
    task = store.enqueue("wf", TaskSpec("a", "A", "noop"))
    assert [e["event_type"] for e in store.events("wf")] == ["ENQUEUED"]
    assert store.get(task)["status"] == "PENDING"


def test_downstream_agent_receives_dependency_output():
    _, store = make_runtime()
    scheduler = DependencyScheduler(store, {
        "research": lambda p: {"facts": ["fact-a"]},
        "writer": lambda p: {"used_facts": p["_dependency_outputs"]["research"]["facts"]},
    })
    result = scheduler.run("wf-deps", [
        TaskSpec("research", "RESEARCH", "research"),
        TaskSpec("writer", "WRITER", "writer", ("research",)),
    ])
    assert result["status"] == "COMPLETED"
    assert result["tasks"][1]["output_json"] == '{"used_facts": ["fact-a"]}'
