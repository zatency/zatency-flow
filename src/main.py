import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from .auth import verify_flow_auth
from .config import settings
from .fsm import DeterministicFlowEngine
from .models import ApprovalRequest, WorkflowRunResponse, WorkflowStartRequest

app = FastAPI(
    title="Zatency Flow",
    version=settings.version,
    description="Deterministic Finite State Machine (FSM) multi-agent orchestrator for enterprise AI.",
)

engine = DeterministicFlowEngine()

RUNS_TOTAL = Counter(
    "zatency_flow_runs_total", "Total FSM workflow runs by terminal/active status", ["status"]
)


@app.middleware("http")
async def tracing_and_security_headers(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or f"zf-req-{uuid.uuid4().hex[:10]}"
    t0 = time.perf_counter()
    response: Response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
    }


@app.get("/ready")
async def readiness() -> dict:
    return {"status": "ready", "default_max_steps": settings.default_max_steps}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post(
    "/v1/runs",
    response_model=WorkflowRunResponse,
    dependencies=[Depends(verify_flow_auth)],
)
async def create_workflow_run(payload: WorkflowStartRequest) -> WorkflowRunResponse:
    try:
        res = engine.start_workflow(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    RUNS_TOTAL.labels(status=res.status.value).inc()
    return res


@app.get(
    "/v1/runs/{run_id}",
    response_model=WorkflowRunResponse,
    dependencies=[Depends(verify_flow_auth)],
)
async def inspect_workflow_run(run_id: str) -> WorkflowRunResponse:
    res = engine.get_run(run_id)
    if res is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return res


@app.post(
    "/v1/runs/{run_id}/approve",
    response_model=WorkflowRunResponse,
    dependencies=[Depends(verify_flow_auth)],
)
async def approve_workflow_step(run_id: str, approval: ApprovalRequest) -> WorkflowRunResponse:
    try:
        res = engine.resolve_approval(run_id, approval)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    RUNS_TOTAL.labels(status=res.status.value).inc()
    return res
