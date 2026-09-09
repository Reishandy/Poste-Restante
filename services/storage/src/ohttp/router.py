import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from starlette import status

from src.ohttp.bhttp import decode_bhttp_request, encode_bhttp_response
from src.ohttp.crypto import decapsulate_request, encapsulate_response

router = APIRouter(tags=["OHTTP Gateway"])


@router.post(
    "/ohttp",
    summary="OHTTP Encapsulated Gateway",
    description="Accepts RFC 9458 encapsulated binary requests and returns encapsulated responses.",
    responses={
        status.HTTP_200_OK: {
            "content": {"message/ohttp-res": {}},
            "description": "Encapsulated OHTTP response",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Outer HPKE decapsulation failure"
        },
    },
)
async def handle_ohttp(request: Request) -> Response:
    raw_body = await request.body()
    priv_key = request.app.state.hpke_private_key

    # Decapsulate outer HPKE envelope
    try:
        bhttp_req_bytes, recipient_ctx, enc = decapsulate_request(raw_body, priv_key)
        bhttp_req = decode_bhttp_request(bhttp_req_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Decapsulation failed: {exc}",
        )

    # In-Memory ASGI Loopback Dispatch
    transport = httpx.ASGITransport(app=request.app)
    dispatch_headers = dict(bhttp_req.headers)
    # Forward the ephemeral token to bypass verify_internal_dispatch
    dispatch_headers["x-internal-dispatch"] = (
        request.app.state.internal_dispatch_token
    )

    async with httpx.AsyncClient(
            transport=transport, base_url="http://internal"
    ) as client:
        internal_resp = await client.request(
            method=bhttp_req.method,
            url=bhttp_req.path,
            headers=dispatch_headers,
            content=bhttp_req.body,
        )

    # Encode inner response to BHTTP
    bhttp_res_bytes = encode_bhttp_response(
        status_code=internal_resp.status_code,
        headers=dict(internal_resp.headers),
        body=internal_resp.content,
    )

    # Encapsulate response
    enc_res_bytes = encapsulate_response(
        bhttp_res_bytes, recipient_ctx, enc
    )

    return Response(
        content=enc_res_bytes,
        media_type="message/ohttp-res",
        status_code=status.HTTP_200_OK,
    )
