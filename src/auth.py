import hmac

from fastapi import Header, HTTPException, status

from .config import settings


async def verify_flow_auth(authorization: str | None = Header(default=None)) -> None:
    """Constant-time Bearer token check when FLOW_GATEWAY_KEY is configured."""
    expected = settings.gateway_api_key
    if not expected:
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Bearer token",
        )

    provided = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid flow gateway credentials",
        )
