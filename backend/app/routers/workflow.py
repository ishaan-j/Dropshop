from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.deps import current_user, user_from_token
from app.limiter import allow
from app.models import AgentRun, AgentSnapshot, Dashboard, Opportunity, ScenarioResult
from app.security import read_token
from app.services.dashboard import agent_snapshots, build_dashboard, opportunities
from app.services.orchestrator import (
    WorkflowError,
    prepare_claims,
    run_demo_scenario,
    run_eligibility_agent,
    run_price_agent,
    run_receipt_agent,
)
from data.repository import repo

router = APIRouter(tags=["workflow"])


@router.get("/dashboard", response_model=Dashboard)
async def dashboard(user_id: str = Depends(current_user)) -> Dashboard:
    return await build_dashboard(user_id)


@router.get("/opportunities", response_model=list[Opportunity])
async def list_opportunities(user_id: str = Depends(current_user)) -> list[Opportunity]:
    return await opportunities(user_id)


@router.get("/agents", response_model=list[AgentSnapshot])
async def agents(user_id: str = Depends(current_user)) -> list[AgentSnapshot]:
    return await agent_snapshots(user_id)


@router.get("/agents/runs", response_model=list[AgentRun])
async def runs(user_id: str = Depends(current_user)) -> list[AgentRun]:
    return await repo.list_runs(user_id)


@router.post("/agents/receipt/run", response_model=AgentRun)
async def run_receipt(user_id: str = Depends(current_user)) -> AgentRun:
    return await _run(run_receipt_agent(user_id, demo=False))


@router.post("/agents/price/run", response_model=AgentRun)
async def run_price(user_id: str = Depends(current_user)) -> AgentRun:
    return await _run(run_price_agent(user_id))


@router.post("/agents/eligibility/run", response_model=AgentRun)
async def run_eligibility(user_id: str = Depends(current_user)) -> AgentRun:
    return await _run(run_eligibility_agent(user_id))


@router.post("/agents/claims/prepare", response_model=AgentRun)
async def prepare(user_id: str = Depends(current_user)) -> AgentRun:
    return await _run(prepare_claims(user_id))


@router.post("/demo/scenario", response_model=ScenarioResult)
async def demo_scenario(user_id: str = Depends(current_user)) -> ScenarioResult:
    if not allow(f"demo:{user_id}", 6):
        raise HTTPException(status_code=429, detail="Too many demo runs.")
    try:
        return await run_demo_scenario(user_id)
    except WorkflowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/agents/stream")
async def stream(token: str) -> StreamingResponse:
    user_id = read_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired.")
    user_from_token(token)
    queue = repo.subscribe()

    async def events():
        try:
            yield "event: hello\ndata: {\"ok\": true}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event.user_id != user_id:
                    continue
                yield f"data: {event.model_dump_json()}\n\n"
        finally:
            repo.unsubscribe(queue)

    return StreamingResponse(events(), media_type="text/event-stream")


async def _run(coro) -> AgentRun:
    try:
        return await coro
    except WorkflowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
