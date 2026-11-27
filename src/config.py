import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "zatency-flow"
    version: str = "0.1.0"
    bind_host: str = os.getenv("BIND_HOST", "0.0.0.0")
    bind_port: int = int(os.getenv("BIND_PORT", "8082"))
    gateway_api_key: str = os.getenv("FLOW_GATEWAY_KEY", "").strip()
    default_max_steps: int = int(os.getenv("DEFAULT_MAX_STEPS", "12"))


settings = Settings()
