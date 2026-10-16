import uuid
from typing import Optional

from pydantic import BaseModel, Field


class PurgeStartResponse(BaseModel):
    """Response for the async manual purge trigger."""
    status: str
    detail: str


class AutoreviewBrandUpdate(BaseModel):
    """Explicit AutoReview brand slug for a project, or null to unlink it."""
    slug: Optional[str] = Field(default=None, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class AutoreviewBrandResponse(BaseModel):
    project_id: uuid.UUID
    autoreview_brand_slug: Optional[str]
