"""Comprehensive evaluation and benchmark suite for UPSC Studio specialist agents and runtime."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from upsc_studio.agents.contracts import (
    AgentRole,
    AgentStatus,
    QualityCheckStatus,
    SPECIALIST_REGISTRY,
)
from upsc_studio.agents.runtime import AgentWorkflowRuntime
from upsc_studio.agents.specialists.factory import get_specialist_agent, list_all_specialists
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.multi_pass import MultiPassResearchWorkflow, MultiPassStatus


def run_evaluation() -> int:
    print("=" * 80)
    print("UPSC STUDIO — AUTONOMOUS AGENTS & RUNTIME EVALUATION BENCHMARK")
    print("=" * 80)

    total_benchmarks = 0
    passed_benchmarks = 0
    failures: list[str] = []

    # -------------------------------------------------------------
    # 1. REGISTRY & SPECIALIST AGENTS AUDIT (All 24 Roles)
    # -------------------------------------------------------------
    print("\n[BENCHMARK 1/7] Specialist Agents Registry & Contract Audit (24 Roles)...")
    total_benchmarks += 1
    all_specialists = list_all_specialists()
    if len(all_specialists) == 24:
        print(f"  -> PASSED: All 24 distinct specialist agents implemented.")
        passed_benchmarks += 1
    else:
        msg = f"Expected 24 specialist agents, found {len(all_specialists)}."
        print(f"  -> FAILED: {msg}")
        failures.append(msg)

    # -------------------------------------------------------------
    # 2. DAG TOPOLOGICAL SORT & DEPENDENCY INTEGRITY
    # -------------------------------------------------------------
    print("\n[BENCHMARK 2/7] DAG Dependency Graph & Cycle Detection...")
    total_benchmarks += 1
    try:
        sorted_specs = AgentWorkflowRuntime._topological_sort(SPECIALIST_REGISTRY)
        seen_ids = set()
        valid_dag = True
        for spec in sorted_specs:
            for dep in spec.dependencies:
                if dep not in seen_ids:
                    valid_dag = False
                    failures.append(f"DAG dependency error: '{dep}' executed after '{spec.agent_id}'.")
            seen_ids.add(spec.agent_id)

        if valid_dag and len(sorted_specs) == 24:
            print("  -> PASSED: DAG is strictly acyclic; all 24 dependencies topologically ordered.")
            passed_benchmarks += 1
        else:
            print("  -> FAILED: DAG topological sort failed or dropped agents.")
    except Exception as exc:
        print(f"  -> FAILED with exception: {exc}")
        failures.append(str(exc))

    # -------------------------------------------------------------
    # 3. TYPED CONTRACTS & FAILURE ISOLATION
    # -------------------------------------------------------------
    print("\n[BENCHMARK 3/7] Typed Contracts & Dependency Blocking Verification...")
    total_benchmarks += 1
    try:
        from upsc_studio.agents.contracts import AgentExecutionContext
        test_dir = Path(tempfile.mkdtemp())
        dummy_context = AgentExecutionContext(
            project_id="p_test_eval",
            project_dir=test_dir,
            run_id="run_test_eval",
            topic_title="Test Topic",
            upstream_outputs={},  # empty upstream outputs
        )
        # Downstream agent with dependencies should be BLOCKED when upstream is missing
        downstream_agent = get_specialist_agent("AGENT_02")
        res_blocked = downstream_agent.run(dummy_context)
        if res_blocked.status == AgentStatus.BLOCKED:
            print("  -> PASSED: Downstream agents block closed when upstream dependencies are incomplete.")
            passed_benchmarks += 1
        else:
            msg = f"Expected BLOCKED, got {res_blocked.status}."
            print(f"  -> FAILED: {msg}")
            failures.append(msg)
    except Exception as exc:
        print(f"  -> FAILED with exception: {exc}")
        failures.append(str(exc))

    # -------------------------------------------------------------
    # 4. PERSISTENT SQLITE WORKFLOW RUNTIME
    # -------------------------------------------------------------
    print("\n[BENCHMARK 4/7] Persistent SQLite Workflow Runtime & Checkpointing...")
    total_benchmarks += 1
    try:
        temp_dir = Path(tempfile.mkdtemp())
        db_path = temp_dir / "eval_workflow.db"
        conn = init_db(db_path)
        proj_mgr = ProjectManager(conn, temp_dir / "projects")
        proj = proj_mgr.create_project(
            ProjectCreate(
                name="Eval Project",
                chapter_title="Fundamental Rights: Nature and Scope",
                exam_cycle="2026",
                cutoff_date="2026-11-26",
                target_duration_min=5,
                tts_enabled=True,
            )
        )

        runtime = AgentWorkflowRuntime(conn, temp_dir / "projects")
        run_id = runtime.create_or_get_workflow(proj.id, target_duration_min=5)

        # Verify duplicate prevention: calling create_or_get_workflow again returns SAME run_id
        run_id_again = runtime.create_or_get_workflow(proj.id, target_duration_min=5)
        if run_id == run_id_again:
            # Check SQLite tables
            t_count = conn.execute("SELECT count(*) as cnt FROM workflow_tasks WHERE run_id = ?", (run_id,)).fetchone()["cnt"]
            if t_count == 24:
                print(f"  -> PASSED: Workflow created with 24 persistent SQLite tasks; duplicate run prevention confirmed.")
                passed_benchmarks += 1
            else:
                msg = f"Expected 24 tasks in SQLite, found {t_count}."
                print(f"  -> FAILED: {msg}")
                failures.append(msg)
        else:
            msg = "Duplicate workflow run created on repeated execution."
            print(f"  -> FAILED: {msg}")
            failures.append(msg)
    except Exception as exc:
        print(f"  -> FAILED with exception: {exc}")
        failures.append(str(exc))

    # -------------------------------------------------------------
    # 5. RECOVERY REVIEW FOR SIDE-EFFECTING TASKS
    # -------------------------------------------------------------
    print("\n[BENCHMARK 5/7] Safe Crash Recovery & Side-Effect Defense...")
    total_benchmarks += 1
    try:
        # Simulate a crash where AGENT_22 (Video Quality Auditor, has_side_effects=True) was EXECUTING
        conn.execute(
            """
            UPDATE workflow_tasks
            SET status = 'EXECUTING'
            WHERE run_id = ? AND agent_id = 'AGENT_22'
            """,
            (run_id,),
        )
        conn.commit()

        recovered = runtime.recover_interrupted_workflows()
        t22 = conn.execute(
            "SELECT status, error_message FROM workflow_tasks WHERE run_id = ? AND agent_id = 'AGENT_22'",
            (run_id,),
        ).fetchone()

        if t22["status"] == "RECOVERY_REVIEW_REQUIRED":
            print("  -> PASSED: Side-effecting task interrupted mid-execution marked RECOVERY_REVIEW_REQUIRED (no blind replay).")
            passed_benchmarks += 1
        else:
            msg = f"Expected RECOVERY_REVIEW_REQUIRED, got {t22['status']}."
            print(f"  -> FAILED: {msg}")
            failures.append(msg)
    except Exception as exc:
        print(f"  -> FAILED with exception: {exc}")
        failures.append(str(exc))

    # -------------------------------------------------------------
    # 6. MULTI-PASS RESEARCH & INSUFFICIENT EVIDENCE DEFENSE
    # -------------------------------------------------------------
    print("\n[BENCHMARK 6/7] Multi-Pass Research & Substantive Fact Checking...")
    total_benchmarks += 1
    try:
        from upsc_studio.research.verifier import EvidenceEngine
        ev_engine = EvidenceEngine(conn, Path(proj.root_dir))
        s_id = ev_engine.add_source(
            project_id=proj.id,
            title="Constitution of India",
            publisher="Ministry of Law and Justice",
            source_tier="PRIMARY_OFFICIAL",
            pub_date="2024-01-01",
        )
        # Add one verified claim and one unsupported claim
        supported_claim_id = ev_engine.add_claim(
            project_id=proj.id,
            statement="Article 14 guarantees equality before the law within the territory of India.",
            chapter_section="Equality",
            source_id=s_id,
            page_or_section="Article 14",
            ref_period="2024",
        )
        ev_engine.verify_claim_against_source(
            claim_id=supported_claim_id,
            source_id=s_id,
            page_or_section="Article 14",
            evidence_excerpt="The State shall not deny to any person equality before the law or equal protection of the laws.",
            reviewer_id="evaluation-fixture-reviewer",
        )
        ev_engine.add_claim(
            project_id=proj.id,
            statement="An unverified claim without source or citation.",
            chapter_section="Unverified Section",
            source_id=None,
            page_or_section=None,
        )

        multi_pass = MultiPassResearchWorkflow(conn, Path(proj.root_dir))
        rep = multi_pass.run_multi_pass_audit(proj.id, proj.chapter_title, "2026-11-26")

        if rep.insufficient_evidence_count > 0 and len(rep.excluded_claims) > 0 and len(rep.safe_narration_claims) > 0:
            print(f"  -> PASSED: {rep.insufficient_evidence_count} unsupported claim(s) isolated from narration as INSUFFICIENT_EVIDENCE.")
            passed_benchmarks += 1
        else:
            msg = "Multi-pass research failed to isolate unsupported claims."
            print(f"  -> FAILED: {msg}")
            failures.append(msg)
    except Exception as exc:
        print(f"  -> FAILED with exception: {exc}")
        failures.append(str(exc))

    # -------------------------------------------------------------
    # 7. SYSTEM AUTOMATION & DISK HEALTH AUDIT
    # -------------------------------------------------------------
    print("\n[BENCHMARK 7/7] System Automation & Health Monitoring...")
    total_benchmarks += 1
    try:
        from upsc_studio.automation.maintenance import SystemMaintenanceEngine
        maint = SystemMaintenanceEngine(conn, temp_dir / "projects")
        h_rep = maint.run_system_health_audit()

        if "disk" in h_rep and "free_gb" in h_rep["disk"]:
            print(f"  -> PASSED: System health audit active. Free disk: {h_rep['disk']['free_gb']} GB ({h_rep['disk']['status']}).")
            passed_benchmarks += 1
        else:
            msg = "Health audit output missing disk metrics."
            print(f"  -> FAILED: {msg}")
            failures.append(msg)
    except Exception as exc:
        print(f"  -> FAILED with exception: {exc}")
        failures.append(str(exc))

    # -------------------------------------------------------------
    # FINAL SUMMARY
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print(f"EVALUATION RESULTS: {passed_benchmarks} / {total_benchmarks} BENCHMARKS PASSED")
    print("=" * 80)

    if failures:
        print("\nFAILURES DETECTED:")
        for idx, f in enumerate(failures, start=1):
            print(f"  {idx}. {f}")
        return 1

    print("\nALL AUTONOMOUS AGENT, DAG RUNTIME, AND QUALITY GATES VERIFIED SUCCESSFULLY.")
    return 0


def run_evaluations(cases_path: Path | None = None) -> dict:
    if cases_path:
        path = cases_path
    else:
        candidates = [
            Path(__file__).parent / "fixtures" / "agent_eval_cases.json",
            Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "agent_eval_cases.json",
            Path("tests") / "fixtures" / "agent_eval_cases.json",
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "agent_eval_cases.json",
        ]
        path = next((p for p in candidates if p.exists()), candidates[0])
    if not path.exists():
        return {"case_count": 0, "passed": 0, "failed": 0, "pass_rate": 1.0, "results": []}
    from upsc_studio.agents.workers import default_worker_handlers
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
    exit_code = run_evaluation()
    fixtures_path = Path(__file__).parent / "fixtures" / "agent_eval_cases.json"
    if fixtures_path.exists():
        fixture_report = run_evaluations(fixtures_path)
        print(f"\nDeterministic Agent Cases: {fixture_report['passed']} / {fixture_report['case_count']} passed.")
        if fixture_report["failed"] > 0:
            exit_code = 1
    sys.exit(exit_code)
