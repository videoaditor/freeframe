"""The agent's own API (`Authorization: Bearer ara_...`). An agent sees only its one project; anything else is 404."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..middleware.auth import get_agent
from ..models.project import Project
from ..services.agents import AgentContext

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/me")
def me(agent: AgentContext = Depends(get_agent), db: Session = Depends(get_db)):
    project = db.get(Project, agent.key.project_id)
    return {"user_id": str(agent.user.id), "name": agent.user.name, "program": agent.key.program,
            "project_id": str(agent.key.project_id), "project_name": project.name if project else ""}
