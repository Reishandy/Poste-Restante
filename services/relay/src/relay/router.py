import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from starlette import status

from src.config import settings
from src.relay import service
from src.relay.dependencies import get_http_client

router = APIRouter(tags=["Relay"])


@router.post(
    "/relay",
    summary="Oblivious HTTP Relay (RFC 9458)",
    description="""
    Blindly forwards an RFC 9458 encapsulated binary request (`message/ohttp-req`)
    to the target upstream gateway and returns the encapsulated response (`message/ohttp-res`).
    The destination must be provided by the client via the `Target-URI` header or `?target=` query parameter.
    """,
    responses={
        status.HTTP_200_OK: {
            "content": {"message/ohttp-res": {}},
            "description": "Successful roundtrip containing encapsulated response.",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Missing target destination URI or empty request payload.",
        },
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "description": "Expected Content-Type: message/ohttp-req.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Upstream gateway unreachable or connection refused.",
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "description": "Upstream gateway connection or read timed out.",
        },
    },
)
@router.post("/ohttp", include_in_schema=False)
async def relay_request(
        request: Request,
        target: str | None = Query(default=None, description="Upstream gateway URI"),
        target_uri: str | None = Header(default=None, alias="Target-URI"),
        http_client: httpx.AsyncClient = Depends(get_http_client),
) -> Response:
    # Verify RFC 9458 Media Type
    content_type = request.headers.get("content-type", "").split(";")[0].strip()
    if content_type != "message/ohttp-req":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be message/ohttp-req",
        )

    # Verify Non-Empty Payload
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body cannot be empty",
        )

    # Resolve Destination URI
    destination_url = target_uri or target
    if not destination_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing target destination URI",
        )

    # Blind Dispatch Upstream
    try:
        upstream_resp = await service.forward_ohttp_request(
            client=http_client,
            target_url=destination_url,
            payload=raw_body,
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.ConnectTimeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream gateway connection timed out",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream gateway timed out",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream gateway unreachable: {exc}",
        )

    # Return Encapsulated Response
    res_content_type = upstream_resp.headers.get("content-type", "message/ohttp-res")
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        media_type=res_content_type,
    )
