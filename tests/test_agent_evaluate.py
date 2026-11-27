from upsc_studio.agents.evaluate import run_evaluations


def test_committed_agent_evaluation_suite_has_no_regressions():
    report = run_evaluations()
    assert report["case_count"] >= 10
    assert report["failed"] == 0, report["results"]
