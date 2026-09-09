import secrets

from fastapi import Header, HTTPException, Request
from starlette import status


def verify_internal_dispatch(
        request: Request,
        x_internal_dispatch: str = Header(
            default="",
            alias="X-Internal-Dispatch",
            include_in_schema=False,
        ),
):
    expected = getattr(request.app.state, "internal_dispatch_token", None)
    if not expected or not secrets.compare_digest(
            x_internal_dispatch, expected
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct HTTP access forbidden. Access via OHTTP gateway only.",
        )
