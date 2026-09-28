from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from contextlib import aclosing
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from ..database import get_db
from ..middleware.auth import get_current_user, get_optional_user
from ..services.whop_auth import require_customer_entitlement
from ..services.auth_service import decode_token, get_user_by_id
from ..models.user import User, UserStatus
from ..services.event_service import event_stream
from ..services.permissions import effective_project_role, is_public_project, is_staff

router = APIRouter(prefix="/events", tags=["events"])

async def customer_event_stream(project_id: str, user: User):
    # An already-open stream must not outlive a revoked Whop entitlement. Reuse
    # the bounded decision cache, and close the Redis subscription on denial.
    async with aclosing(event_stream(project_id)) as stream:
        async for message in stream:
            try:
                await run_in_threadpool(require_customer_entitlement, user)
            except HTTPException:
                return
            yield message


@router.get("/{project_id}")
async def stream_events(
    project_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_optional_user),
):
    # EventSource can't send Authorization headers, so accept token as query param
    user = current_user
    if not user and token:
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            user = get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user or user.status == UserStatus.deactivated:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    await run_in_threadpool(require_customer_entitlement, user)

    # Verify user has access to this project
    if not effective_project_role(db, project_id, user) and not (is_staff(user) and is_public_project(db, project_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")

    return StreamingResponse(
        customer_event_stream(str(project_id), user)
        if isinstance(user.suite_account_id, str) and user.suite_account_id
        else event_stream(str(project_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
