from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_and_readiness() -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_hitl_pause_and_resume_with_idempotency() -> None:
    payload = {
        "workflow_name": "enterprise-wire-approval",
        "tenant_id": "acme-corp",
        "idempotency_key": "idem-wire-2026-001",
        "entry_step_id": "step_kyc",
        "steps": [
            {
                "step_id": "step_kyc",
                "tool_name": "verify_kyc_policy",
                "arguments": {"customer_id": "CUST-404"},
                "on_success_next": "step_reserve",
            },
            {
                "step_id": "step_reserve",
                "tool_name": "reserve_erp_budget",
                "arguments": {"cost_center": "FIN-APAC", "amount_usd": 25000},
                "requires_approval": True,
                "on_success_next": "step_settle",
            },
            {
                "step_id": "step_settle",
                "tool_name": "dispatch_wire_settlement",
                "arguments": {"beneficiary": "VENDOR-99", "amount_usd": 25000},
                "on_success_next": None,
            },
        ],
    }

    r1 = client.post("/v1/runs", json=payload)
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["status"] == "WAITING_APPROVAL"
    assert body1["pending_step_id"] == "step_reserve"

    # Idempotent replay returns exact same run_id without duplicate execution
    r_dup = client.post("/v1/runs", json=payload)
    assert r_dup.json()["run_id"] == body1["run_id"]

    # Approve HITL checkpoint to complete workflow
    r2 = client.post(
        f"/v1/runs/{body1['run_id']}/approve",
        json={"approver_id": "cfo@acme.com", "approved": True},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "COMPLETED"
    assert r2.json()["steps_executed"] == 3


def test_saga_rollback_on_downstream_failure() -> None:
    res = client.post(
        "/v1/runs",
        json={
            "workflow_name": "failed-settlement-saga",
            "entry_step_id": "reserve",
            "steps": [
                {
                    "step_id": "reserve",
                    "tool_name": "reserve_erp_budget",
                    "arguments": {"cost_center": "OPS-01", "amount_usd": 9000},
                    "on_success_next": "settle",
                },
                {
                    "step_id": "settle",
                    "tool_name": "dispatch_wire_settlement",
                    "arguments": {
                        "beneficiary": "VENDOR-12",
                        "amount_usd": 9000,
                        "simulate_failure": True,
                    },
                },
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ROLLED_BACK"
    assert "reserve" in data["compensations_executed"]


def test_bounded_cycle_cap_blocks_infinite_agent_loops() -> None:
    res = client.post(
        "/v1/runs",
        json={
            "workflow_name": "cyclic-agent-loop",
            "max_steps": 3,
            "entry_step_id": "loop_node",
            "steps": [
                {
                    "step_id": "loop_node",
                    "tool_name": "verify_kyc_policy",
                    "arguments": {"customer_id": "CUST-LOOP"},
                    "on_success_next": "loop_node",
                }
            ],
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "FAILED_CYCLE_CAP"
    assert res.json()["steps_executed"] == 3
