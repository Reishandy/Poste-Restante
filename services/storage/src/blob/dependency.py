import secrets

from fastapi import HTTPException, Request
from starlette import status


def verify_internal_dispatch(request: Request):
    internal_token = request.headers.get("x-internal-dispatch", "")
    expected = getattr(request.app.state, "internal_dispatch_token", None)

    if not expected or not secrets.compare_digest(internal_token, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct HTTP access forbidden. Access via OHTTP gateway only.",
        )
