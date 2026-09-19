from fastapi import Header, HTTPException, status

from .config import settings


async def verify_edge_token(
    authorization: str | None = Header(default=None),
):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    expected = f"Bearer {settings.edge_api_token}"

    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )

    return True