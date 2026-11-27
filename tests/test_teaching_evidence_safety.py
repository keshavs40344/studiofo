"""Teaching engine must not turn unverified notes into factual narration."""

import pytest

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.teaching.engine import TeachingEngine


def test_teaching_engine_blocks_when_no_claims_are_attested(tmp_path):
    conn = init_db(tmp_path / "teaching.db")
    manager = ProjectManager(conn, tmp_path / "projects")
    project = manager.create_project(
        ProjectCreate(name="Teaching Safety", chapter_title="Fundamental Rights")
    )
    engine = TeachingEngine(conn, tmp_path / "projects")
    with pytest.raises(ValueError, match="no claims have explicit human evidence attestation"):
        engine.generate_teaching_package(
            project_id=project.id,
            chapter_title=project.chapter_title,
            chapter_map={},
            notes_excerpt="Article 32 provides a constitutional remedy.",
            target_duration_min=5,
        )


def test_teaching_engine_ignores_legacy_verified_status_without_attestation(tmp_path):
    conn = init_db(tmp_path / "legacy.db")
    manager = ProjectManager(conn, tmp_path / "projects")
    project = manager.create_project(
        ProjectCreate(name="Legacy Status", chapter_title="Fundamental Rights")
    )
    conn.execute(
        """INSERT INTO sources (id, project_id, title, publisher, url, pub_date, access_date, source_tier, notes)
        VALUES ('src_test', ?, 'Constitution', 'Government of India', NULL, NULL, '2026-11-27', 'PRIMARY_OFFICIAL', '')""",
        (project.id,),
    )
    conn.execute(
        """INSERT INTO claims (id, project_id, statement, chapter_section, scene_id, source_id,
        page_or_section, ref_period, status, verification_notes)
        VALUES ('clm_test', ?, 'Article 32 provides a constitutional remedy.', 'Remedies', NULL,
        'src_test', 'Article 32', NULL, 'VERIFIED', 'Legacy SQL status without reviewer excerpt')""",
        (project.id,),
    )
    conn.commit()

    engine = TeachingEngine(conn, tmp_path / "projects")
    with pytest.raises(ValueError, match="no claims have explicit human evidence attestation"):
        engine.generate_teaching_package(
            project_id=project.id,
            chapter_title=project.chapter_title,
            chapter_map={},
            target_duration_min=5,
        )
