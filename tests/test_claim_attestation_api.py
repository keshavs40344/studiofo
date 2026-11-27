"""API tests for project-scoped human evidence attestation."""

from fastapi.testclient import TestClient

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.web.app import create_app
from upsc_studio.research.verifier import EvidenceEngine


def test_attestation_endpoint_requires_excerpt_and_project_scope(tmp_path):
    db_path = tmp_path / "api.db"
    projects_root = tmp_path / "projects"
    conn = init_db(db_path)
    manager = ProjectManager(conn, projects_root)
    project = manager.create_project(
        ProjectCreate(name="Attestation API", chapter_title="Article 32")
    )
    engine = EvidenceEngine(conn, Path(project.root_dir))
    source_id = engine.add_source(
        project.id, "Constitution of India", "Government of India", "PRIMARY_OFFICIAL"
    )
    claim_id = engine.add_claim(
        project.id, "Article 32 provides a constitutional remedy.", "Remedies",
        source_id=source_id, page_or_section="Article 32"
    )

    client = TestClient(create_app(db_path=db_path, projects_root=projects_root))
    listed = client.get(f"/api/projects/{project.id}/claims")
    assert listed.status_code == 200
    assert listed.json()["total_claims"] == 1
    assert listed.json()["claims"][0]["id"] == claim_id

    response = client.post(
        f"/api/projects/{project.id}/claims/{claim_id}/attest",
        json={
            "source_id": source_id,
            "page_or_section": "Article 32, Clause 1",
            "evidence_excerpt": "The right to move the Supreme Court by appropriate proceedings for enforcement of Part III rights.",
            "reviewer_id": "local-reviewer",
        },
    )
    assert response.status_code == 200
    assert response.json()["identity_authenticated"] is False

    row = conn.execute("SELECT status, verification_notes FROM claims WHERE id = ?", (claim_id,)).fetchone()
    assert row["status"] == "VERIFIED"
    assert row["verification_notes"].startswith("HUMAN_ATTESTED_BY:local-reviewer")


def test_attestation_endpoint_rejects_missing_or_cross_project_claim(tmp_path):
    db_path = tmp_path / "api-scope.db"
    projects_root = tmp_path / "projects"
    conn = init_db(db_path)
    manager = ProjectManager(conn, projects_root)
    first = manager.create_project(ProjectCreate(name="First Project", chapter_title="Article 32"))
    second = manager.create_project(ProjectCreate(name="Second Project", chapter_title="Article 14"))
    engine = EvidenceEngine(conn, Path(first.root_dir))
    source_id = engine.add_source(first.id, "Constitution", "Government of India", "PRIMARY_OFFICIAL")
    claim_id = engine.add_claim(first.id, "Article 32 provides a constitutional remedy.", "Remedies")

    client = TestClient(create_app(db_path=db_path, projects_root=projects_root))
    cross_project = client.post(
        f"/api/projects/{second.id}/claims/{claim_id}/attest",
        json={
            "source_id": source_id,
            "page_or_section": "Article 32",
            "evidence_excerpt": "A sufficiently long source excerpt.",
            "reviewer_id": "reviewer",
        },
    )
    assert cross_project.status_code == 404

    missing_excerpt = client.post(
        f"/api/projects/{first.id}/claims/{claim_id}/attest",
        json={
            "source_id": source_id,
            "page_or_section": "Article 32",
            "evidence_excerpt": "short",
            "reviewer_id": "reviewer",
        },
    )
    assert missing_excerpt.status_code == 400
