"""
Agent API

REST API endpoints for managing the aria.hermes autonomous agent.
"""

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.auth.dependencies import get_current_user, require_permissions
from hermes.auth.models import User
from hermes.services.database import get_db

router = APIRouter(prefix="/agent", tags=["Agent"])

# Global agent instance
_agent = None
_agent_task = None


class AgentConfigUpdate(BaseModel):
    """Request model for updating agent config."""
    auto_fix_regressions: Optional[bool] = None
    auto_apply_high_confidence: Optional[bool] = None
    high_confidence_threshold: Optional[float] = None
    stale_benchmark_hours: Optional[int] = None
    min_improvement_threshold: Optional[float] = None
    learning_enabled: Optional[bool] = None


async def get_agent():
    """Get the global agent instance."""
    global _agent
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return _agent


@router.get(
    "/status",
    summary="Get agent status",
)
async def get_agent_status(
    user: User = Depends(get_current_user),
):
    """Get the current status of the aria.hermes agent."""
    global _agent
    
    if _agent is None:
        return {
            "agent_id": "aria.hermes",
            "status": "not_initialized",
            "running": False,
        }
    
    return _agent.get_status()


@router.post(
    "/start",
    summary="Start the agent",
)
async def start_agent(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions(["agent:manage"])),
):
    """Start the aria.hermes autonomous agent."""
    global _agent, _agent_task
    
    if _agent is not None and _agent._running:
        raise HTTPException(status_code=400, detail="Agent already running")
    
    from hermes.agents.hermes_agent import create_hermes_agent
    
    _agent = await create_hermes_agent(db)
    
    # Start in background
    async def run_agent():
        await _agent.start()
    
    _agent_task = asyncio.create_task(run_agent())
    
    return {"status": "starting", "message": "Agent is starting"}


@router.post(
    "/stop",
    summary="Stop the agent",
)
async def stop_agent(
    user: User = Depends(require_permissions(["agent:manage"])),
):
    """Stop the aria.hermes autonomous agent."""
    global _agent, _agent_task
    
    if _agent is None or not _agent._running:
        raise HTTPException(status_code=400, detail="Agent not running")
    
    await _agent.stop()
    
    if _agent_task:
        _agent_task.cancel()
        _agent_task = None
    
    return {"status": "stopped", "message": "Agent has been stopped"}


@router.put(
    "/config",
    summary="Update agent configuration",
)
async def update_agent_config(
    config: AgentConfigUpdate,
    user: User = Depends(require_permissions(["agent:manage"])),
):
    """Update the agent's configuration."""
    global _agent
    
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    updates = {k: v for k, v in config.model_dump().items() if v is not None}
    _agent.update_config(updates)
    
    return {"status": "updated", "config": _agent.config}


@router.get(
    "/tasks",
    summary="Get agent task queue",
)
async def get_agent_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=100),
    user: User = Depends(get_current_user),
):
    """Get the agent's task queue."""
    global _agent
    
    if _agent is None:
        return {"tasks": [], "total": 0}
    
    tasks = []
    
    # Get pending tasks
    for task in _agent.task_queue[:limit]:
        if status is None or task.status == status:
            tasks.append({
                "id": str(task.id),
                "type": task.type.value,
                "priority": task.priority.value,
                "prompt_id": str(task.prompt_id) if task.prompt_id else None,
                "description": task.description,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
            })
    
    # Get active tasks
    for task in _agent.active_tasks.values():
        if status is None or task.status == status:
            tasks.append({
                "id": str(task.id),
                "type": task.type.value,
                "priority": task.priority.value,
                "prompt_id": str(task.prompt_id) if task.prompt_id else None,
                "description": task.description,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
            })
    
    return {
        "tasks": tasks[:limit],
        "total": len(_agent.task_queue) + len(_agent.active_tasks),
    }


@router.post(
    "/tasks/{prompt_id}/optimize",
    summary="Queue optimization task",
)
async def queue_optimization(
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions(["agent:manage"])),
):
    """Manually queue an optimization task for a prompt."""
    global _agent
    
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    import uuid
    from hermes.agents.hermes_agent import TaskType, Priority
    
    from hermes.services.prompt_store import PromptStoreService
    prompt_store = PromptStoreService(db)
    prompt = await prompt_store.get(uuid.UUID(prompt_id))
    
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    _agent._add_task(
        TaskType.PROACTIVE_OPTIMIZE,
        Priority.HIGH,
        prompt.id,
        f"Manual optimization request for {prompt.name}",
        {"prompt": prompt},
    )
    
    return {
        "status": "queued",
        "message": f"Optimization task queued for {prompt.name}",
    }


@router.post(
    "/tasks/{prompt_id}/benchmark",
    summary="Queue benchmark task",
)
async def queue_benchmark(
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permissions(["agent:manage"])),
):
    """Manually queue a benchmark task for a prompt."""
    global _agent
    
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    import uuid
    from hermes.agents.hermes_agent import TaskType, Priority
    
    from hermes.services.prompt_store import PromptStoreService
    prompt_store = PromptStoreService(db)
    prompt = await prompt_store.get(uuid.UUID(prompt_id))
    
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    _agent._add_task(
        TaskType.BENCHMARK_STALE,
        Priority.HIGH,
        prompt.id,
        f"Manual benchmark request for {prompt.name}",
        {"prompt": prompt},
    )
    
    return {
        "status": "queued",
        "message": f"Benchmark task queued for {prompt.name}",
    }


@router.get(
    "/metrics",
    summary="Get agent metrics",
)
async def get_agent_metrics(
    user: User = Depends(get_current_user),
):
    """Get detailed agent performance metrics."""
    global _agent
    
    if _agent is None:
        return {
            "status": "not_initialized",
            "metrics": None,
        }
    
    status = _agent.get_status()
    
    return {
        "status": "running" if _agent._running else "stopped",
        "metrics": status["metrics"],
        "config": status["config"],
        "queue_depth": status["queue"]["pending"] + status["queue"]["active"],
    }
