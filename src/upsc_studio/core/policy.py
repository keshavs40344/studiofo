"""Budget, cloud, and privacy policy enforcement for UPSC Studio."""

from __future__ import annotations

from dataclasses import asdict, dataclass


class PaidActionBlockedError(PermissionError):
    """Raised when a paid API, asset purchase, or unapproved cloud upload is attempted."""


@dataclass(frozen=True)
class BudgetAndCloudPolicy:
    FREE_FIRST: bool = True
    LOCAL_FIRST: bool = True
    PAID_SERVICES_ENABLED: bool = False
    PAID_API_CALLS_ENABLED: bool = False
    PAID_ASSET_PURCHASES_ENABLED: bool = False
    CLOUD_PROCESSING_OPTIONAL: bool = True
    CLOUD_UPLOAD_REQUIRES_APPROVAL: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_POLICY = BudgetAndCloudPolicy()


def require_paid_approval(
    provider: str,
    purpose: str,
    estimated_cost_inr: float,
    free_alternative_reason: str,
    policy: BudgetAndCloudPolicy = DEFAULT_POLICY,
    explicit_user_approved: bool = False,
) -> None:
    """Block any paid service or API call unless explicitly enabled and approved."""
    if not (policy.PAID_SERVICES_ENABLED and policy.PAID_API_CALLS_ENABLED and explicit_user_approved):
        raise PaidActionBlockedError(
            f"Paid action blocked by policy: provider={provider}, purpose='{purpose}', "
            f"estimated_cost_inr={estimated_cost_inr}, reason='{free_alternative_reason}'."
        )


def require_cloud_upload_approval(
    provider: str,
    policy: BudgetAndCloudPolicy = DEFAULT_POLICY,
    explicit_user_approved: bool = False,
) -> None:
    """Block uploading private notes or recordings to cloud services without explicit approval."""
    if policy.CLOUD_UPLOAD_REQUIRES_APPROVAL and not explicit_user_approved:
        raise PaidActionBlockedError(
            f"Cloud upload to '{provider}' requires explicit user approval."
        )
