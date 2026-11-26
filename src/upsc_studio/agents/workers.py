"""Deterministic specialist workers that can be registered with DependencyScheduler.

These workers validate supplied project data; they do not fabricate research, sources,
syllabus mappings, media assets or language-model outputs.
"""
from __future__ import annotations

import re
from typing import Any


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def topic_profile(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an explicitly selected content category; never infer it from title alone."""
    allowed = {"upsc", "general_knowledge", "current_affairs", "deep_dive"}
    category = str(payload.get("category", "")).strip().casefold()
    if category not in allowed:
        return {"status": "REVIEW_REQUIRED", "error": "Explicit supported category is required",
                "allowed_categories": sorted(allowed)}
    cutoff = payload.get("cutoff_date")
    if category == "current_affairs" and not cutoff:
        return {"status": "BLOCKED", "error": "Current-affairs projects require an explicit cutoff_date"}
    return {"status": "COMPLETED", "category": category, "cutoff_date": cutoff,
            "syllabus_mapping_enabled": category == "upsc"}


def coverage_audit(payload: dict[str, Any]) -> dict[str, Any]:
    """Check declared required concepts against supplied script text; substring evidence only."""
    required = payload.get("required_concepts", [])
    script = payload.get("script_text", "")
    if not isinstance(required, list) or not all(isinstance(x, str) and x.strip() for x in required):
        return {"status": "BLOCKED", "error": "required_concepts must be a list of non-empty strings"}
    if not isinstance(script, str) or not script.strip():
        return {"status": "BLOCKED", "error": "script_text is missing"}
    haystack = _normalise(script)
    covered = [term for term in required if _normalise(term) in haystack]
    missing = [term for term in required if term not in covered]
    return {"status": "PASSED" if not missing else "FAILED",
            "required_count": len(required), "covered": covered, "missing": missing,
            "limitation": "Literal/normalised text matching only; semantic coverage requires independent review."}


def evidence_completeness_audit(payload: dict[str, Any]) -> dict[str, Any]:
    """Flag claims without attached source references or explicit dates."""
    claims = payload.get("claims", [])
    if not isinstance(claims, list):
        return {"status": "BLOCKED", "error": "claims must be a list"}
    missing = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            missing.append({"index": index, "reason": "claim_not_object"})
            continue
        if not claim.get("text"):
            missing.append({"index": index, "reason": "claim_text_missing"})
        if not claim.get("source_refs"):
            missing.append({"index": index, "reason": "source_refs_missing"})
        if not claim.get("source_date"):
            missing.append({"index": index, "reason": "source_date_missing"})
    return {"status": "PASSED" if not missing else "REVIEW_REQUIRED",
            "claim_count": len(claims), "issues": missing,
            "limitation": "Metadata completeness is not proof that a source supports a claim."}


def rights_asset_audit(payload: dict[str, Any]) -> dict[str, Any]:
    """Block release when an asset lacks explicit provenance and rights status."""
    assets = payload.get("assets", [])
    if not isinstance(assets, list):
        return {"status": "BLOCKED", "error": "assets must be a list"}
    issues = []
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            issues.append({"index": index, "reason": "asset_not_object"})
            continue
        if not asset.get("asset_ref"):
            issues.append({"index": index, "reason": "asset_ref_missing"})
        if not asset.get("source_url") and not asset.get("origin"):
            issues.append({"index": index, "reason": "provenance_missing"})
        if asset.get("rights_status") not in {"OWNED", "LICENSED", "PUBLIC_DOMAIN", "PERMITTED"}:
            issues.append({"index": index, "reason": "rights_not_verified"})
    return {"status": "PASSED" if not issues else "FAILED",
            "asset_count": len(assets), "issues": issues}


def release_gate(payload: dict[str, Any]) -> dict[str, Any]:
    """Combine independent gate results; approval is deliberately separate."""
    gates = payload.get("gates", {})
    if not isinstance(gates, dict) or not gates:
        return {"status": "BLOCKED", "failed_gates": ["gate_results_missing"]}
    failed = [name for name, result in gates.items()
              if not isinstance(result, dict) or result.get("status") not in {"PASSED", "COMPLETED"}]
    if not payload.get("human_release_approval", False):
        failed.append("human_release_approval_missing")
    return {"status": "RELEASE_READY" if not failed else "BLOCKED",
            "failed_gates": failed, "public_upload_authorized": False,
            "note": "Release readiness never triggers upload; public publishing remains a separate explicit action."}


def default_worker_handlers() -> dict[str, Any]:
    return {
        "topic_profile": topic_profile,
        "coverage_audit": coverage_audit,
        "evidence_completeness_audit": evidence_completeness_audit,
        "rights_asset_audit": rights_asset_audit,
        "release_gate": release_gate,
    }
