from collections.abc import Callable
from typing import Any


class ToolExecutionError(Exception):
    """Raised when a deterministic tool contract fails validation or upstream execution."""


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


class EnterpriseToolRegistry:
    """Schema-checked enterprise tool registry with paired Saga compensating actions."""

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self._compensators: dict[str, ToolHandler] = {}
        self._required_fields: dict[str, list[str]] = {}
        self._register_builtin_sandbox_tools()

    def register(
        self,
        name: str,
        handler: ToolHandler,
        required_fields: list[str] | None = None,
        compensator: ToolHandler | None = None,
    ) -> None:
        self._handlers[name] = handler
        self._required_fields[name] = required_fields or []
        if compensator is not None:
            self._compensators[name] = compensator

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._handlers:
            raise ToolExecutionError(f"Unregistered tool '{name}'")

        for field in self._required_fields.get(name, []):
            if field not in arguments or arguments[field] in (None, ""):
                raise ToolExecutionError(f"Tool '{name}' missing required argument '{field}'")

        return self._handlers[name](arguments)

    def compensate(self, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        comp = self._compensators.get(name)
        if comp is None:
            return None
        return comp(arguments)

    def _register_builtin_sandbox_tools(self) -> None:
        self.register(
            name="verify_kyc_policy",
            required_fields=["customer_id"],
            handler=lambda args: {
                "customer_id": args["customer_id"],
                "kyc_status": "VERIFIED",
                "risk_tier": "LOW",
            },
        )
        self.register(
            name="reserve_erp_budget",
            required_fields=["cost_center", "amount_usd"],
            handler=lambda args: {
                "reservation_id": f"RES-{args['cost_center']}-901",
                "amount_usd": args["amount_usd"],
                "state": "RESERVED",
            },
            compensator=lambda args: {
                "cost_center": args["cost_center"],
                "state": "RELEASED_COMPENSATED",
            },
        )
        self.register(
            name="dispatch_wire_settlement",
            required_fields=["beneficiary", "amount_usd"],
            handler=lambda args: (
                (_ for _ in ()).throw(ToolExecutionError("Upstream banking rail timeout"))
                if args.get("simulate_failure")
                else {
                    "settlement_id": f"WIRE-{args['beneficiary']}-772",
                    "status": "SETTLED",
                }
            ),
        )
