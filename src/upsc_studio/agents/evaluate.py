"""Run the committed deterministic agent evaluation cases."""
from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.agents.workers import default_worker_handlers


def run_evaluations(cases_path: Path | None = None) -> dict:
    if cases_path is not None:
        path = Path(cases_path)
    else:
        repository_fixture = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "agent_eval_cases.json"
        packaged_fixture = Path(__file__).parent / "fixtures" / "agent_eval_cases.json"
        path = repository_fixture if repository_fixture.is_file() else packaged_fixture
    if not path.is_file():
        raise FileNotFoundError(f"Agent evaluation fixture not found: {path}")
    cases = json.loads(path.read_text(encoding="utf-8"))
    handlers = default_worker_handlers()
    results = []
    for case in cases:
        handler = handlers.get(case["worker"])
        if handler is None:
            actual = "ERROR"
            detail = "unknown worker"
        else:
            try:
                output = handler(case["input"])
                actual = output.get("status", "MISSING_STATUS")
                detail = output
            except Exception as exc:
                actual = "ERROR"
                detail = f"{type(exc).__name__}: {exc}"
        results.append({
            "id": case["id"],
            "expected": case["expected_status"],
            "actual": actual,
            "passed": actual == case["expected_status"],
            "detail": detail,
        })
    passed = sum(item["passed"] for item in results)
    return {"case_count": len(results), "passed": passed, "failed": len(results) - passed,
            "pass_rate": passed / len(results) if results else 0.0, "results": results}


if __name__ == "__main__":
    report = run_evaluations()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["failed"] == 0 else 1)
