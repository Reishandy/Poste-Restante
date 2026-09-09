import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from starlette import status

from src.ohttp.bhttp import decode_bhttp_request, encode_bhttp_response
from src.ohttp.crypto import decapsulate_request, encapsulate_response

router = APIRouter(tags=["OHTTP Gateway"])


@router.post(
    "/ohttp",
    tags=["OHTTP Gateway"],
    summary="Oblivious HTTP Gateway (RFC 9458)",
    description="""
    Processes an RFC 9458 encapsulated HTTP message.
    
    ### Ciphersuite
    * **Key ID:** `1`
    * **KEM:** `DHKEM(X25519, HKDF-SHA256)` (`0x0020`)
    * **KDF:** `HKDF-SHA256` (`0x0001`)
    * **AEAD:** `AES-256-GCM` (`0x0002`)
    
    ### Wire Protocol
    1. Outer payload: `header (7 bytes) || enc (32 bytes) || ciphertext`.
    2. Decapsulated body is parsed as a Binary HTTP request (RFC 9292).
    3. The request is dispatched internally to `/mailbox/{id}` via in-memory loopback.
    4. The inner response is re-encoded as BHTTP and sealed with HPKE response encapsulation.
    
    *Note:* An outer status `200 OK` indicates successful envelope decapsulation; inner application errors (such as `400 Bad Request`) are encapsulated inside the returning `message/ohttp-res` payload.
    """,
    responses={
        status.HTTP_200_OK: {
            "content": {"message/ohttp-res": {}},
            "description": "Successful roundtrip; body contains HPKE-sealed BHTTP response.",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Malformed envelope, unparseable BHTTP, or mismatched ciphersuite parameters.",
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
