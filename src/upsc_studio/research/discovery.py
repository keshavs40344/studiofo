"""Conservative, free-first research discovery.

Discovery registers source candidates as OTHER and never creates VERIFIED claims.
A live result or abstract is not proof that it supports a specific statement.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from upsc_studio.research.verifier import EvidenceEngine


class ResearchDiscovery:
    """Discover bibliographic and background source candidates for human review."""

    CROSSREF_URL = "https://api.crossref.org/works"
    WIKIPEDIA_URL = "https://en.wikipedia.org/w/api.php"
    BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, evidence: EvidenceEngine, session: requests.Session | None = None) -> None:
        self.evidence = evidence
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "UPSC-Studio-ResearchDiscovery/1.0 (source discovery; no automated fact verification)",
            "Accept": "application/json",
        })

    @staticmethod
    def _date_parts(item: dict[str, Any]) -> str | None:
        for key in ("published-print", "published-online", "published", "created"):
            value = item.get(key)
            parts = value.get("date-parts") if isinstance(value, dict) else None
            if parts and parts[0]:
                vals = [int(v) for v in parts[0]]
                if len(vals) >= 3:
                    return f"{vals[0]:04d}-{vals[1]:02d}-{vals[2]:02d}"
                if len(vals) == 2:
                    return f"{vals[0]:04d}-{vals[1]:02d}-01"
                if len(vals) == 1:
                    return f"{vals[0]:04d}-01-01"
        return None

    @staticmethod
    def _abstract_text(value: str | None) -> str:
        if not value:
            return ""
        return " ".join(BeautifulSoup(value, "html.parser").get_text(" ").split())[:1200]

    def _crossref(self, query: str, limit: int) -> list[dict[str, Any]]:
        params = {"query.bibliographic": query, "rows": min(limit, 10), "select": "DOI,title,author,publisher,published,published-print,published-online,created,URL,type,abstract"}
        contact = os.getenv("UPSC_STUDIO_CONTACT_EMAIL")
        if contact:
            params["mailto"] = contact
        response = self.session.get(self.CROSSREF_URL, params=params, timeout=(5, 15))
        response.raise_for_status()
        message = response.json().get("message", {})
        results: list[dict[str, Any]] = []
        for item in message.get("items", []):
            titles = item.get("title") or []
            title = str(titles[0]).strip() if titles else ""
            url = str(item.get("URL") or "").strip()
            if not title or not url:
                continue
            authors = item.get("author") or []
            publisher = str(item.get("publisher") or "Crossref-indexed publisher")
            results.append({
                "title": title[:300],
                "publisher": publisher[:200],
                "url": url,
                "pub_date": self._date_parts(item),
                "provider": "Crossref",
                "snippet": self._abstract_text(item.get("abstract")),
                "record_type": item.get("type"),
                "doi": item.get("DOI"),
                "source_tier": "OTHER",
                "review_note": "Bibliographic discovery candidate only; confirm publication type, publisher, date and relevance manually.",
            })
        return results

    def _wikipedia(self, query: str, limit: int) -> list[dict[str, Any]]:
        params = {
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": min(limit, 10),
        }
        response = self.session.get(self.WIKIPEDIA_URL, params=params, timeout=(5, 15))
        response.raise_for_status()
        results: list[dict[str, Any]] = []
        for item in response.json().get("query", {}).get("search", []):
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            results.append({
                "title": title[:300],
                "publisher": "Wikipedia contributors",
                "url": "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_")),
                "pub_date": None,
                "provider": "Wikipedia",
                "snippet": BeautifulSoup(str(item.get("snippet") or ""), "html.parser").get_text(" ")[:1000],
                "source_tier": "OTHER",
                "review_note": "Tertiary background only; do not use as the sole authority for legal, statistical or current-affairs claims.",
            })
        return results

    def _brave(self, query: str, limit: int) -> list[dict[str, Any]]:
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return []
        response = self.session.get(
            self.BRAVE_URL,
            params={"q": query, "count": min(limit, 10)},
            headers={"X-Subscription-Token": api_key},
            timeout=(5, 15),
        )
        response.raise_for_status()
        results: list[dict[str, Any]] = []
        for item in response.json().get("web", {}).get("results", []):
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            if not title or not url or not url.startswith(("https://", "http://")):
                continue
            raw_date = item.get("page_age") or item.get("published")
            pub_date = str(raw_date)[:10] if raw_date else None
            results.append({
                "title": title[:300],
                "publisher": str(item.get("meta_url", {}).get("hostname") or "Web publisher")[:200],
                "url": url,
                "pub_date": pub_date,
                "provider": "Brave Search",
                "snippet": str(item.get("description") or "")[:1000],
                "source_tier": "OTHER",
                "review_note": "Search result metadata only; open the original page and verify publication date and factual support.",
            })
        return results

    def discover(
        self,
        project_id: str,
        query: str,
        limit: int = 8,
        cutoff_date: str | None = None,
        require_dated_sources: bool = False,
    ) -> dict[str, Any]:
        """Search configured providers and register non-verified source candidates."""
        q = " ".join(query.split())
        if len(q) < 4:
            raise ValueError("Research query must contain at least four non-space characters.")
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10.")
        cutoff: date | None = None
        if cutoff_date:
            try:
                cutoff = date.fromisoformat(cutoff_date)
            except ValueError as exc:
                raise ValueError("cutoff_date must use YYYY-MM-DD.") from exc

        providers: dict[str, str] = {}
        candidates: list[dict[str, Any]] = []
        for name, fn in (
            ("Crossref", self._crossref),
            ("Wikipedia", self._wikipedia),
            ("Brave Search", self._brave),
        ):
            try:
                found = fn(q, limit)
                providers[name] = "AVAILABLE" if found else (
                    "NOT_CONFIGURED" if name == "Brave Search" and not os.getenv("BRAVE_SEARCH_API_KEY")
                    else "NO_RESULTS"
                )
                candidates.extend(found)
            except Exception as exc:
                providers[name] = f"ERROR: {type(exc).__name__}: {str(exc)[:240]}"

        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in candidates:
            url = item["url"].strip()
            if url in seen:
                continue
            seen.add(url)
            item_date: date | None = None
            if item.get("pub_date"):
                try:
                    item_date = date.fromisoformat(str(item["pub_date"])[:10])
                except ValueError:
                    item["pub_date"] = None
            if require_dated_sources and item_date is None:
                continue
            if cutoff and item_date and item_date > cutoff:
                continue
            if require_dated_sources and cutoff and item_date and item_date > cutoff:
                continue
            deduped.append(item)

        existing = {
            row["url"]: row["id"]
            for row in self.evidence.conn.execute(
                "SELECT id, url FROM sources WHERE project_id = ? AND url IS NOT NULL",
                (project_id,),
            ).fetchall()
        }
        registered: list[dict[str, Any]] = []
        for item in deduped[:limit]:
            source_id = existing.get(item["url"])
            if source_id is None:
                notes = (
                    f"DISCOVERED_BY={item['provider']}\n"
                    f"REVIEW_REQUIRED={item['review_note']}\n"
                    f"SNIPPET={item['snippet']}"
                )
                source_id = self.evidence.add_source(
                    project_id=project_id,
                    title=item["title"],
                    publisher=item["publisher"],
                    source_tier="OTHER",
                    url=item["url"],
                    pub_date=item.get("pub_date"),
                    notes=notes,
                )
            registered.append({
                "source_id": source_id,
                **item,
                "verification_status": "HUMAN_REVIEW_REQUIRED",
                "duplicate": item["url"] in existing,
            })

        status = "DISCOVERY_RESULTS_REGISTERED" if registered else "NO_CANDIDATES_FOUND"
        return {
            "status": status,
            "query": q,
            "registered_count": len(registered),
            "providers": providers,
            "candidates": registered,
            "cutoff_date": cutoff_date,
            "fact_checking": "NOT_PERFORMED; sources are candidates and no claim is marked VERIFIED",
        }
