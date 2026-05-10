"""
Workflow management API.
"""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agents.workflow import WorkflowState, create_default_workflow, default_workflow
from app.auth import TokenData, get_optional_user

router = APIRouter()


class WorkflowRunRequest(BaseModel):
    query: str
    session_id: str | None = None
    user_id: str | None = None
    knowledge_id: str | None = None


class WorkflowRunResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]
    evaluation: dict[str, float]
    node_latencies: dict[str, int]
    status: str


class WorkflowInfo(BaseModel):
    id: str
    name: str
    description: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


@router.get("/", response_model=WorkflowInfo)
async def get_workflow_info(
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Get current workflow configuration."""
    wf = default_workflow
    info = wf.to_dict()
    return WorkflowInfo(**info)


@router.post("/run", response_model=WorkflowRunResponse)
async def run_workflow(
    request: WorkflowRunRequest,
    current_user: TokenData | None = Depends(get_optional_user),
):
    """Run the workflow with a query."""
    wf = create_default_workflow()

    state = WorkflowState(
        query=request.query,
        session_id=request.session_id or "",
        user_id=request.user_id or "",
        knowledge_id=request.knowledge_id,
    )

    result = await wf.run(state)

    return WorkflowRunResponse(
        answer=result.answer,
        sources=result.sources,
        evaluation=result.evaluation,
        node_latencies=result.node_latencies,
        status=result.status,
    )


@router.get("/nodes")
async def list_nodes(
    current_user: TokenData | None = Depends(get_optional_user),
):
    """List all workflow nodes."""
    wf = default_workflow
    return {
        "nodes": [
            {
                "id": n.id,
                "name": n.name,
                "type": n.node_type.value,
                "next": n.next_nodes,
            }
            for n in wf.nodes.values()
        ]
    }
