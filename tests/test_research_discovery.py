"""Research discovery registers candidates without asserting factual verification."""
from __future__ import annotations

from pathlib import Path

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.discovery import ResearchDiscovery
from upsc_studio.research.verifier import EvidenceEngine


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.headers = {}

    def get(self, url, params=None, headers=None, timeout=None):
        if "crossref" in url:
            return FakeResponse(self.responses["crossref"])
        if "wikipedia" in url:
            return FakeResponse(self.responses["wikipedia"])
        raise AssertionError(f"Unexpected provider request: {url}")


def test_discovery_registers_crossref_and_wikipedia_as_unverified_candidates(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "discovery.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Discovery", chapter_title="Urban heat islands")
    )
    fake = FakeSession({
        "crossref": {"message": {"items": [{
            "title": ["Urban heat and public health"],
            "URL": "https://doi.org/10.1000/example",
            "DOI": "10.1000/example",
            "publisher": "Academic Publisher",
            "type": "journal-article",
            "published": {"date-parts": [[2024, 5, 1]]},
            "abstract": "<jats:p>Urban temperature patterns and public health effects.</jats:p>",
        }]}},
        "wikipedia": {"query": {"search": [{
            "title": "Urban heat island",
            "snippet": "An urban area that is significantly warmer.",
        }]}},
    })
    result = ResearchDiscovery(EvidenceEngine(conn, Path(project.root_dir)), fake).discover(
        project.id, "urban heat island", limit=5
    )

    assert result["status"] == "DISCOVERY_RESULTS_REGISTERED"
    assert result["registered_count"] == 2
    assert all(item["verification_status"] == "HUMAN_REVIEW_REQUIRED" for item in result["candidates"])
    assert all(item["source_tier"] == "OTHER" for item in result["candidates"])
    assert conn.execute(
        "SELECT COUNT(*) FROM claims WHERE project_id = ?", (project.id,)
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM sources WHERE project_id = ?", (project.id,)
    ).fetchone()[0] == 2


def test_current_affairs_discovery_excludes_undated_and_post_cutoff_candidates(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "current.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(
            name="Current affairs",
            chapter_title="Energy policy developments",
            content_category="current_affairs",
            cutoff_date="2026-11-27",
        )
    )
    fake = FakeSession({
        "crossref": {"message": {"items": [
            {"title": ["Within cutoff"], "URL": "https://doi.org/10.1000/in",
             "publisher": "Publisher", "published": {"date-parts": [[2026, 11, 20]]}},
            {"title": ["After cutoff"], "URL": "https://doi.org/10.1000/out",
             "publisher": "Publisher", "published": {"date-parts": [[2026, 11, 28]]}},
            {"title": ["Undated"], "URL": "https://doi.org/10.1000/none",
             "publisher": "Publisher"},
        ]}},
        "wikipedia": {"query": {"search": [{"title": "Energy policy", "snippet": "General background"}]}},
    })
    result = ResearchDiscovery(EvidenceEngine(conn, Path(project.root_dir)), fake).discover(
        project.id,
        "energy policy developments",
        cutoff_date=project.cutoff_date,
        require_dated_sources=True,
    )
    assert [item["title"] for item in result["candidates"]] == ["Within cutoff"]
