from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED_CYCLE_CAP = "FAILED_CYCLE_CAP"


class WorkflowStep(BaseModel):
    step_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = Field(default=False)
    on_success_next: str | None = Field(default=None)


class WorkflowStartRequest(BaseModel):
    workflow_name: str = Field(..., min_length=1)
    tenant_id: str = Field(default="default", min_length=1)
    idempotency_key: str | None = Field(default=None)
    max_steps: int = Field(default=12, ge=1, le=50)
    entry_step_id: str = Field(..., min_length=1)
    steps: list[WorkflowStep] = Field(..., min_length=1, max_length=50)


class ApprovalRequest(BaseModel):
    approver_id: str = Field(..., min_length=1)
    approved: bool = Field(default=True)
    comment: str = Field(default="")


class TransitionEvent(BaseModel):
    step_index: int
    step_id: str
    tool_name: str
    outcome: str
    output: dict[str, Any] = Field(default_factory=dict)
    timestamp_ms: float


class WorkflowRunResponse(BaseModel):
    run_id: str
    workflow_name: str
    tenant_id: str
    status: RunStatus
    steps_executed: int
    max_steps: int
    pending_step_id: str | None = None
    compensations_executed: list[str] = Field(default_factory=list)
    trace: list[TransitionEvent] = Field(default_factory=list)
