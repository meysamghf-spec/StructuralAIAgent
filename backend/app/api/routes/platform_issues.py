"""Platform issues admin API (/api/v1/admin/platform-issues) and the user's own issue list.

Auth for /admin: ``Authorization: Bearer <PLATFORM_ISSUE_ADMIN_TOKEN>`` (machine access, e.g. Grok Bot) or a signed-in
account listed in PLATFORM_ADMIN_ACCOUNTS (account id or e-mail). Nothing here changes code or deploys anything.
"""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_auth_service, get_current_account
from app.application.auth_service import AuthService
from app.application.platform_helper_factory import get_helper_service
from app.domain.models.user import AuthenticatedAccount
from app.platform_helper.issues import KIND_FEATURE_REQUEST, OPEN_STATUSES, STATUSES

router = APIRouter(tags=["platform-issues"])


def require_admin(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    authorization: Annotated[str | None, Header()] = None,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
) -> str:
    svc = get_helper_service()
    token = svc.settings.admin_token
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization.split(" ", 1)[1].strip()
        if token and hmac.compare_digest(supplied.encode(), token.encode()):
            return "machine-admin"
    try:
        acc = get_current_account(auth_service, authorization, x_actor_id)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Admin credentials required") from None
    allowed = svc.settings.admin_accounts
    if allowed and (acc.account_id.lower() in allowed or (acc.email or "").lower() in allowed):
        return acc.account_id
    raise HTTPException(status_code=403, detail="Platform admin access required")


Admin = Annotated[str, Depends(require_admin)]


class PostBackBody(BaseModel):
    status: str | None = Field(default=None, description="/".join(STATUSES))
    fix_note: str | None = Field(default=None, max_length=1000, description="Shown to the user in chat")
    fix_pr_url: str | None = Field(default=None, max_length=500)
    proposed_fix: dict[str, Any] | None = Field(default=None, description="{kind: diff|pr_draft, title, body, diff} — stored as draft")


class ProposeFixBody(BaseModel):
    kind: str = Field(default="pr_draft", pattern="^(diff|pr_draft)$")
    title: str = Field(max_length=200)
    body: str = Field(default="", max_length=8000)
    diff: str = Field(default="", max_length=60000)


@router.get("/admin/platform-issues")
def list_issues(_: Admin, status: str | None = None, open_only: bool = False, limit: int = 100,
                kind: str | None = None) -> dict[str, Any]:
    """``kind=feature_request`` lists only auto-reported missing-capability requests; ``kind=bug`` everything else."""
    if kind not in (None, "", "bug", KIND_FEATURE_REQUEST):
        raise HTTPException(status_code=422, detail="kind must be 'bug' or 'feature_request'")
    svc = get_helper_service()
    statuses = OPEN_STATUSES if open_only else ((status,) if status else None)
    if kind == KIND_FEATURE_REQUEST:
        items = svc.store.list(statuses=statuses, limit=limit, category=KIND_FEATURE_REQUEST)
    else:
        items = svc.store.list(statuses=statuses, limit=500 if kind == "bug" else limit)
        if kind == "bug":
            items = [i for i in items if i.kind == "bug"][:limit]
    if kind == KIND_FEATURE_REQUEST:  # most requested first, then newest
        items = sorted(items, key=lambda i: (-i.occurrences, i.created_at.timestamp() * -1))
    return {"items": [i.to_dict() for i in items], "count": len(items), "helper": svc.status()}


@router.get("/admin/platform-issues/{issue_id}")
def get_issue(issue_id: str, _: Admin) -> dict[str, Any]:
    issue = get_helper_service().store.get(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue.to_dict()


@router.post("/admin/platform-issues/{issue_id}/post-back")
def post_back(issue_id: str, body: PostBackBody, _: Admin) -> dict[str, Any]:
    try:
        issue = get_helper_service().issues.post_back(issue_id, status=body.status, fix_note=body.fix_note,
                                                      fix_pr_url=body.fix_pr_url, proposed_fix=body.proposed_fix)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue.to_dict()


@router.post("/admin/platform-issues/{issue_id}/propose-fix")
def propose_fix(issue_id: str, body: ProposeFixBody, _: Admin) -> dict[str, Any]:
    """Store a proposed fix as a DRAFT and mark the issue awaiting approval. It is never applied automatically."""
    issue = get_helper_service().issues.post_back(
        issue_id, status="awaiting_approval",
        proposed_fix={"kind": body.kind, "title": body.title, "body": body.body, "diff": body.diff, "status": "draft"})
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue.to_dict()


@router.post("/admin/platform-issues/{issue_id}/approve-fix")
def approve_fix(issue_id: str, who: Admin) -> dict[str, Any]:
    """Human approval flag on the draft. Still does NOT merge or deploy: that is done by a person in GitHub."""
    svc = get_helper_service()
    issue = svc.store.get(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    if who == "machine-admin":
        raise HTTPException(status_code=403, detail="Fix approval needs a signed-in human admin, not the machine token")
    if not issue.proposed_fix:
        raise HTTPException(status_code=409, detail="No proposed fix to approve")
    updated = svc.issues.post_back(issue_id, status="fix_ready", proposed_fix={**issue.proposed_fix, "status": "approved", "approved_by": who})
    return updated.to_dict() if updated else {}


@router.get("/platform-issues/mine")
def my_issues(account: Annotated[AuthenticatedAccount, Depends(get_current_account)], limit: int = 20) -> dict[str, Any]:
    items = get_helper_service().store.list(account_id=account.account_id, limit=limit)
    return {"items": [{"id": i.id, "title": i.title, "status": i.status, "severity": i.severity,
                       "fix_note": i.fix_note, "fix_pr_url": i.fix_pr_url, "occurrences": i.occurrences,
                       "created_at": i.created_at.isoformat(), "updated_at": i.updated_at.isoformat()} for i in items]}


@router.get("/platform-helper/status")
def helper_status(_: Annotated[AuthenticatedAccount, Depends(get_current_account)]) -> dict[str, Any]:
    st = get_helper_service().status()
    return {"llm_configured": st["llm_configured"], "keyless_fallback": any(p["keyless"] for p in st["providers"]),
            "provider_count": len(st["providers"])}


@router.get("/platform-helper/admin-check")
def admin_check(who: Admin) -> dict[str, str]:
    return {"admin": who}
