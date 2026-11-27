"""Project-category persistence and non-UPSC pipeline regression tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.pipeline.staged import StagedChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.teaching.engine import TeachingEngine
from upsc_studio.research.verifier import EvidenceEngine


def test_legacy_database_migrates_to_upsc_category_by_default(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(db_path)
    legacy.execute(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            chapter_title TEXT NOT NULL,
            exam_cycle TEXT NOT NULL,
            cutoff_date TEXT NOT NULL,
            target_duration_min INTEGER NOT NULL DEFAULT 30,
            tts_enabled INTEGER NOT NULL DEFAULT 0,
            root_dir TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'NOT_STARTED',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    legacy.execute(
        """
        INSERT INTO projects
        (id, name, slug, chapter_title, exam_cycle, cutoff_date, root_dir, created_at, updated_at)
        VALUES ('old-project', 'Old', 'old', 'Old topic', 'UPSC CSE 2026',
                '2026-11-26', 'C:/old', '2026-01-01', '2026-01-01')
        """
    )
    legacy.commit()
    legacy.close()

    conn = init_db(db_path)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
    assert "content_category" in columns
    assert conn.execute(
        "SELECT content_category FROM projects WHERE id = 'old-project'"
    ).fetchone()["content_category"] == "upsc"


def test_project_category_survives_portable_backup_restore(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "source.db")
    manager = ProjectManager(conn, tmp_path / "source_projects")
    project = manager.create_project(
        ProjectCreate(
            name="Climate current affairs",
            chapter_title="Urban heat action plans",
            content_category="current_affairs",
            cutoff_date="2026-11-27",
        )
    )
    marker = Path(project.root_dir) / "research" / "source_notes.md"
    marker.write_text("Source notes stay in the portable backup.", encoding="utf-8")
    backup = manager.backup_project(project.id, tmp_path / "backups")

    restored_conn = init_db(tmp_path / "restored.db")
    restored_manager = ProjectManager(restored_conn, tmp_path / "restored_projects")
    restored = restored_manager.restore_project(backup)

    assert restored.content_category == "current_affairs"
    assert (Path(restored.root_dir) / "research" / "source_notes.md").read_text(
        encoding="utf-8"
    ) == "Source notes stay in the portable backup."


def test_general_knowledge_uses_topic_map_instead_of_upsc_syllabus(
    tmp_path: Path, monkeypatch
) -> None:
    conn = init_db(tmp_path / "general.db")
    manager = ProjectManager(conn, tmp_path / "projects")
    project = manager.create_project(
        ProjectCreate(
            name="GK rivers",
            chapter_title="River systems of India",
            content_category="general_knowledge",
        )
    )
    pipeline = StagedChapterPipeline(conn, tmp_path / "projects")
    paths = pipeline._paths(Path(project.root_dir))
    paths["notes"].write_text(
        "# Major river systems\n# Drainage basins\nUser supplied notes, not verified research.",
        encoding="utf-8",
    )

    def forbidden_upsc_map(*args, **kwargs):
        raise AssertionError("UPSC syllabus engine must not run for general knowledge")

    monkeypatch.setattr(
        "upsc_studio.pipeline.staged.SyllabusEngine.map_chapter",
        forbidden_upsc_map,
    )
    report = pipeline._stage_academic(
        project.id, Path(project.root_dir), paths, project
    )
    topic_map = __import__("json").loads(
        (Path(project.root_dir) / "research" / "topic_map.json").read_text(encoding="utf-8")
    )

    assert report["status"] == "COMPLETED"
    assert topic_map["content_category"] == "general_knowledge"
    assert topic_map["coverage_status"] == "REVIEW_REQUIRED"
    assert "Major river systems" in [topic["title"] for topic in topic_map["topics"]]
    assert conn.execute(
        "SELECT COUNT(*) AS c FROM coverage_ledger WHERE project_id = ?",
        (project.id,),
    ).fetchone()["c"] == 0


def test_non_upsc_teaching_outputs_are_category_labelled_not_prelims_mains(
    tmp_path: Path,
) -> None:
    conn = init_db(tmp_path / "teaching.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(
            name="Deep dive",
            chapter_title="Ocean circulation",
            content_category="deep_dive",
        )
    )
    summary = TeachingEngine(conn, Path(project.root_dir)).generate_teaching_package(
        project_id=project.id,
        chapter_title=project.chapter_title,
        chapter_map={
            "content_category": "deep_dive",
            "primary_papers": [],
            "topic_dimensions": [{"title": "Ocean circulation"}],
        },
        content_category="deep_dive",
        target_duration_min=5,
    )
    root = Path(project.root_dir)
    assert summary["content_category"] == "deep_dive"
    assert (root / "teaching" / "topic_context.md").is_file()
    assert (root / "teaching" / "analysis_framework.md").is_file()
    assert not (root / "teaching" / "prelims_track.md").exists()
    assert not (root / "teaching" / "mains_track.md").exists()
    qbank = __import__("json").loads(
        (root / "teaching" / "question_bank.json").read_text(encoding="utf-8")
    )
    assert qbank["content_category"] == "deep_dive"
    assert qbank["practice_prompts"][0]["label"] == "PRACTICE_PROMPT_REVIEW_REQUIRED"


def test_non_upsc_academic_qa_does_not_demand_upsc_coverage_rows(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "qa.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(
            name="Current affairs QA",
            chapter_title="Recent energy policy developments",
            content_category="current_affairs",
        )
    )
    qa = QAAuditor(conn, Path(project.root_dir))._check_academic(project.id)
    assert not any("UPSC syllabus coverage" in issue for issue in qa["blocking_issues"])
    assert any("Category topic map is missing" in issue for issue in qa["blocking_issues"])

def test_current_affairs_rejects_sources_after_the_project_cutoff(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "cutoff.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(
            name="Current affairs cutoff",
            chapter_title="Recent climate policy",
            content_category="current_affairs",
            cutoff_date="2026-11-27",
        )
    )
    EvidenceEngine(conn, Path(project.root_dir)).add_source(
        project.id,
        "Future-dated report",
        "Official publisher",
        "PRIMARY_OFFICIAL",
        url="https://example.gov/future-report",
        pub_date="2026-11-28",
    )
    qa = QAAuditor(conn, Path(project.root_dir))._check_academic(project.id)
    assert any(
        "on or before the project cutoff" in issue for issue in qa["blocking_issues"]
    )
