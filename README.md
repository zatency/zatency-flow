# Zatency Flow

**Deterministic Finite State Machine (FSM) Multi-Agent Orchestrator for Enterprise AI.**

Replaces unbounded, non-deterministic LLM loops with state-bounded execution graphs—enforcing strict step-cycle caps, type-safe tool contracts, idempotency keys, automatic Saga rollbacks, and zero-compute Human-in-the-Loop (HITL) approval checkpoints.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Engineered by Zatency](https://img.shields.io/badge/Engineered%20by-Zatency-0f172a.svg)](https://zatency.com)

---

## Architecture Overview

```text
                       ┌──────────────────────────────────────┐
                       │  Agent / Enterprise App / API Client │
                       │  POST /v1/runs  (Idempotency-Key)    │
                       └──────────────────┬───────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        Zatency Flow Deterministic Runtime                       │
│                                                                                 │
│  1. Bounded FSM Scheduler      ──► Enforces max_steps cycle caps (no runaways)  │
│  2. Schema Tool Validator      ──► Validates required inputs before execution   │
│  3. HITL Checkpoint Gate       ──► Pauses at WAITING_APPROVAL (0 GPU cycles)    │
│  4. Durable Saga Compensator   ──► Rewinds committed steps in reverse on failure│
└─────────────────────────────────────────┬───────────────────────────────────────┘
                                          │
                                          ▼
                       ┌──────────────────────────────────────┐
                       │  Immutable Execution Trace & Metrics │
                       │  (Step transitions + Saga audit log) │
                       └──────────────────────────────────────┘
```

### Core Capabilities
* **Bounded Cycle Caps (`max_steps`):** Terminates cyclic agent graphs deterministically (`FAILED_CYCLE_CAP`) before runaway token spend occurs.
* **Zero-Compute HITL Suspension:** Suspends workflow state at `WAITING_APPROVAL` until an authorized operator approves via `POST /v1/runs/{run_id}/approve`.
* **Automatic Saga Compensations:** Tracks committed side effects on a rollback stack and executes paired compensating handlers in reverse order on downstream errors (`ROLLED_BACK`).
* **Idempotent Execution:** Deduplicates retried workflow submissions by `(tenant_id, idempotency_key)` so financial and ERP mutations execute once.

---

## Quickstart (30 Seconds)

```bash
git clone https://github.com/zatency/zatency-flow.git
cd zatency-flow
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests
python -m pytest -v
uvicorn src.main:app --host 0.0.0.0 --port 8082
```

---

## Observability Endpoints
* **`GET /health`** — Service liveness probe.
* **`GET /ready`** — Readiness probe and default cycle-cap configuration.
* **`GET /metrics`** — Prometheus exposition endpoint (`zatency_flow_runs_total`).

---

## Open-Core vs. Enterprise Edition

| Capability | Community Edition (Apache 2.0) | Zatency Flow Enterprise |
| :--- | :---: | :---: |
| Bounded FSM scheduler & `max_steps` cycle guards | ✅ | ✅ |
| Schema-checked tool registry & idempotency keys | ✅ | ✅ |
| HITL approval checkpoints & Saga rollbacks | ✅ | ✅ |
| Durable Temporal.io / PostgreSQL state persistence | Roadmap | ✅ |
| Native Slack / Microsoft Teams interactive approval cards | — | ✅ |
| Constrained XGrammar / JSON-Schema LLM token decoding | — | ✅ |
| Immutable SOC 2 / HIPAA / EU AI Act workflow ledger | — | ✅ |

Need durable Temporal.io deployment, custom ERP connectors, or enterprise SLAs?  
👉 **[Schedule an Architecture Session at zatency.com](https://zatency.com/contact)**

## License
Licensed under the [Apache License 2.0](LICENSE).
