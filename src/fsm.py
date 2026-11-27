import time
import uuid
from dataclasses import dataclass, field

from .models import (
    ApprovalRequest,
    RunStatus,
    TransitionEvent,
    WorkflowRunResponse,
    WorkflowStartRequest,
    WorkflowStep,
)
from .tools import EnterpriseToolRegistry, ToolExecutionError


@dataclass
class RunRecord:
    run_id: str
    workflow_name: str
    tenant_id: str
    status: RunStatus
    max_steps: int
    steps_map: dict[str, WorkflowStep]
    current_step_id: str | None
    steps_executed: int = 0
    completed_stack: list[WorkflowStep] = field(default_factory=list)
    compensations_executed: list[str] = field(default_factory=list)
    trace: list[TransitionEvent] = field(default_factory=list)

    def to_response(self) -> WorkflowRunResponse:
        pending = (
            self.current_step_id
            if self.status == RunStatus.WAITING_APPROVAL
            else None
        )
        return WorkflowRunResponse(
            run_id=self.run_id,
            workflow_name=self.workflow_name,
            tenant_id=self.tenant_id,
            status=self.status,
            steps_executed=self.steps_executed,
            max_steps=self.max_steps,
            pending_step_id=pending,
            compensations_executed=list(self.compensations_executed),
            trace=list(self.trace),
        )


class DeterministicFlowEngine:
    """Bounded Finite State Machine (FSM) orchestrator with HITL pause & Saga rollbacks."""

    def __init__(self) -> None:
        self.tools = EnterpriseToolRegistry()
        self._runs: dict[str, RunRecord] = {}
        self._idempotency_index: dict[tuple[str, str], str] = {}

    def start_workflow(self, req: WorkflowStartRequest) -> WorkflowRunResponse:
        if req.idempotency_key:
            idem_key = (req.tenant_id, req.idempotency_key)
            existing_id = self._idempotency_index.get(idem_key)
            if existing_id and existing_id in self._runs:
                return self._runs[existing_id].to_response()

        steps_map = {s.step_id: s for s in req.steps}
        if req.entry_step_id not in steps_map:
            raise ValueError(f"Entry step '{req.entry_step_id}' not found in workflow steps")

        run_id = f"zf-{uuid.uuid4().hex[:12]}"
        record = RunRecord(
            run_id=run_id,
            workflow_name=req.workflow_name,
            tenant_id=req.tenant_id,
            status=RunStatus.RUNNING,
            max_steps=req.max_steps,
            steps_map=steps_map,
            current_step_id=req.entry_step_id,
        )
        self._runs[run_id] = record
        if req.idempotency_key:
            self._idempotency_index[(req.tenant_id, req.idempotency_key)] = run_id

        self._advance(record, approval_granted=False)
        return record.to_response()

    def get_run(self, run_id: str) -> WorkflowRunResponse | None:
        rec = self._runs.get(run_id)
        return rec.to_response() if rec else None

    def resolve_approval(self, run_id: str, approval: ApprovalRequest) -> WorkflowRunResponse:
        rec = self._runs.get(run_id)
        if not rec:
            raise KeyError(f"Workflow run '{run_id}' not found")
        if rec.status != RunStatus.WAITING_APPROVAL or not rec.current_step_id:
            raise ValueError(f"Workflow run '{run_id}' is not awaiting approval")

        if not approval.approved:
            self._rollback(rec, reason=f"Rejected by {approval.approver_id}")
            return rec.to_response()

        rec.status = RunStatus.RUNNING
        self._advance(rec, approval_granted=True)
        return rec.to_response()

    def _advance(self, rec: RunRecord, approval_granted: bool) -> None:
        first_iteration = True
        while rec.current_step_id is not None:
            if rec.steps_executed >= rec.max_steps:
                rec.status = RunStatus.FAILED_CYCLE_CAP
                return

            step = rec.steps_map.get(rec.current_step_id)
            if step is None:
                self._rollback(rec, reason=f"Unknown target step '{rec.current_step_id}'")
                return

            if step.requires_approval and not (first_iteration and approval_granted):
                rec.status = RunStatus.WAITING_APPROVAL
                return

            first_iteration = False
            rec.steps_executed += 1

            try:
                output = self.tools.execute(step.tool_name, step.arguments)
            except ToolExecutionError as exc:
                rec.trace.append(
                    TransitionEvent(
                        step_index=rec.steps_executed,
                        step_id=step.step_id,
                        tool_name=step.tool_name,
                        outcome="FAILED",
                        output={"error": str(exc)},
                        timestamp_ms=round(time.time() * 1000, 2),
                    )
                )
                self._rollback(rec, reason=str(exc))
                return

            rec.completed_stack.append(step)
            rec.trace.append(
                TransitionEvent(
                    step_index=rec.steps_executed,
                    step_id=step.step_id,
                    tool_name=step.tool_name,
                    outcome="SUCCEEDED",
                    output=output,
                    timestamp_ms=round(time.time() * 1000, 2),
                )
            )
            rec.current_step_id = step.on_success_next

        rec.status = RunStatus.COMPLETED

    def _rollback(self, rec: RunRecord, reason: str) -> None:
        while rec.completed_stack:
            prior_step = rec.completed_stack.pop()
            comp_out = self.tools.compensate(prior_step.tool_name, prior_step.arguments)
            if comp_out is not None:
                rec.compensations_executed.append(prior_step.step_id)
                rec.trace.append(
                    TransitionEvent(
                        step_index=rec.steps_executed,
                        step_id=prior_step.step_id,
                        tool_name=f"{prior_step.tool_name}:compensate",
                        outcome="COMPENSATED",
                        output={"reason": reason, **comp_out},
                        timestamp_ms=round(time.time() * 1000, 2),
                    )
                )
        rec.current_step_id = None
        rec.status = RunStatus.ROLLED_BACK
