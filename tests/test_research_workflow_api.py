"""Research source and human-claim verification API tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from upsc_studio.web.app import create_app


def test_dashboard_research_source_claim_and_human_verification_flow(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "research.db",
        projects_root=tmp_path / "research_projects",
    )
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={
            "name": "Research workflow",
            "chapter_title": "Water governance",
            "content_category": "general_knowledge",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["id"]

    source_response = client.post(
        f"/api/projects/{project_id}/sources",
        json={
            "title": "Official water governance report",
            "publisher": "Government Research Agency",
            "source_tier": "PRIMARY_OFFICIAL",
            "url": "https://example.gov/water-report",
            "pub_date": "2025-08-01",
        },
    )
    assert source_response.status_code == 200
    source_id = source_response.json()["source_id"]

    claim_response = client.post(
        f"/api/projects/{project_id}/claims",
        json={
            "statement": "The report describes an integrated approach to basin planning.",
            "chapter_section": "Planning approach",
            "source_id": source_id,
        },
    )
    assert claim_response.status_code == 200
    claim_id = claim_response.json()["claim_id"]
    assert claim_response.json()["status"] == "HUMAN_REVIEW_REQUIRED"

    wrong_url = client.post(
        f"/api/projects/{project_id}/sources",
        json={
            "title": "Invalid URL source",
            "publisher": "Publisher",
            "source_tier": "OTHER",
            "url": "file:///private/data",
        },
    )
    assert wrong_url.status_code == 422

    verified = client.post(
        f"/api/projects/{project_id}/claims/{claim_id}/verify",
        json={
            "source_id": source_id,
            "page_or_section": "Page 14, section 3.2",
            "evidence_excerpt": (
                "The report describes an integrated approach to basin planning "
                "across the relevant administrative levels."
            ),
            "reviewer": "Human Reviewer",
        },
    )
    assert verified.status_code == 200
    assert verified.json()["status"] == "VERIFIED"
    assert verified.json()["verification_method"] == "HUMAN_ATTESTED_SOURCE_EXCERPT"
    assert "does not independently prove" in verified.json()["limitation"]

    ledger = client.get(f"/api/projects/{project_id}/research")
    assert ledger.status_code == 200
    assert ledger.json()["content_category"] == "general_knowledge"
    assert any(item["id"] == source_id for item in ledger.json()["sources"])
    assert next(item for item in ledger.json()["claims"] if item["id"] == claim_id)["status"] == "VERIFIED"


def test_claim_cannot_be_verified_against_another_projects_source(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "isolation.db",
        projects_root=tmp_path / "isolated_projects",
    )
    client = TestClient(app)

    def make_project(name):
        response = client.post(
            "/api/projects",
            json={"name": name, "chapter_title": "Test subject"},
        )
        assert response.status_code == 200
        return response.json()["id"]

    first = make_project("First project")
    second = make_project("Second project")
    source_response = client.post(
        f"/api/projects/{second}/sources",
        json={
            "title": "Second project source",
            "publisher": "Official publisher",
            "source_tier": "PRIMARY_OFFICIAL",
            "url": "https://example.gov/second",
        },
    )
    source_id = source_response.json()["source_id"]
    claim_response = client.post(
        f"/api/projects/{first}/claims",
        json={
            "statement": "This is an atomic claim that needs careful source review.",
            "chapter_section": "Introduction",
        },
    )
    claim_id = claim_response.json()["claim_id"]
    rejected = client.post(
        f"/api/projects/{first}/claims/{claim_id}/verify",
        json={
            "source_id": source_id,
            "page_or_section": "Page 1",
            "evidence_excerpt": "This excerpt is long enough for a linkage test.",
            "reviewer": "Reviewer",
        },
    )
    assert rejected.status_code == 404
