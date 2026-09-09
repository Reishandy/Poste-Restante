import secrets
import struct

import httpx
from pyhpke import AEADId, CipherSuite, KDFId, KEMId
from src.relay.router import get_http_client
from starlette import status

SUITE = CipherSuite.new(
    KEMId.DHKEM_X25519_HKDF_SHA256, KDFId.HKDF_SHA256, AEADId.AES256_GCM
)


async def test_relay_rejects_non_ohttp_content_type(client):
    response = await client.post(
        "/relay",
        content=b"arbitrary-data",
        headers={
            "content-type": "application/json",
            "Target-URI": "http://storage.internal/ohttp",
        },
    )
    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert "Content-Type must be message/ohttp-req" in response.json()["detail"]


async def test_relay_rejects_empty_payload(client):
    response = await client.post(
        "/relay",
        content=b"",
        headers={
            "content-type": "message/ohttp-req",
            "Target-URI": "http://storage.internal/ohttp",
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Request body cannot be empty" in response.json()["detail"]


async def test_relay_rejects_missing_target_destination(client):
    response = await client.post(
        "/relay",
        content=b"encapsulated-bytes",
        headers={"content-type": "message/ohttp-req"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Missing target destination URI" in response.json()["detail"]


async def test_relay_accepts_target_via_query_param(client, test_app):
    requested_url = ""

    def capture_url_handler(request: httpx.Request) -> httpx.Response:
        nonlocal requested_url
        requested_url = str(request.url)
        return httpx.Response(
            status_code=200,
            content=b"mock-response",
            headers={"content-type": "message/ohttp-res"},
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(capture_url_handler))
    test_app.dependency_overrides[get_http_client] = lambda: mock_client

    try:
        response = await client.post(
            "/relay?target=http://storage.internal:8000/ohttp",
            content=b"valid-payload",
            headers={"content-type": "message/ohttp-req"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert requested_url == "http://storage.internal:8000/ohttp"
    finally:
        test_app.dependency_overrides.clear()


async def test_relay_upstream_unreachable_returns_502(client, test_app):
    def unreachable_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused by storage host", request=request)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(unreachable_handler))
    test_app.dependency_overrides[get_http_client] = lambda: mock_client

    try:
        response = await client.post(
            "/relay",
            content=b"sample-payload",
            headers={
                "content-type": "message/ohttp-req",
                "Target-URI": "http://storage.internal/ohttp",
            },
        )
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Upstream gateway unreachable" in response.json()["detail"]
    finally:
        test_app.dependency_overrides.clear()


async def test_relay_upstream_timeout_returns_504(client, test_app):
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Storage node timed out", request=request)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler))
    test_app.dependency_overrides[get_http_client] = lambda: mock_client

    try:
        response = await client.post(
            "/relay",
            content=b"sample-payload",
            headers={
                "content-type": "message/ohttp-req",
                "Target-URI": "http://storage.internal/ohttp",
            },
        )
        assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
        assert "Upstream gateway timed out" in response.json()["detail"]
    finally:
        test_app.dependency_overrides.clear()


async def test_relay_strips_client_headers(client, test_app):
    forwarded_headers: dict[str, str] = {}

    def inspect_headers_handler(request: httpx.Request) -> httpx.Response:
        nonlocal forwarded_headers
        forwarded_headers = dict(request.headers)
        return httpx.Response(
            status_code=200,
            content=b"response-data",
            headers={"content-type": "message/ohttp-res"},
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(inspect_headers_handler))
    test_app.dependency_overrides[get_http_client] = lambda: mock_client

    try:
        await client.post(
            "/relay",
            content=b"payload",
            headers={
                "content-type": "message/ohttp-req",
                "Target-URI": "http://storage.internal/ohttp",
                "User-Agent": "PosteRestanteClient/1.0",
                "Authorization": "Bearer token-12345",
                "X-Client-Location": "Bali",
                "Cookie": "session_id=fake",
            },
        )
        # Verify only the message/ohttp-req content type was forwarded
        assert forwarded_headers.get("content-type") == "message/ohttp-req"
        assert "authorization" not in forwarded_headers
        assert "x-client-location" not in forwarded_headers
        assert "cookie" not in forwarded_headers
        assert "user-agent" not in forwarded_headers or "PosteRestanteClient" not in forwarded_headers["user-agent"]
    finally:
        test_app.dependency_overrides.clear()


async def test_relay_end_to_end_ohttp_roundtrip(client, test_app):
    """Verifies that encapsulated cipher bytes pass through the relay bit-for-bit uncorrupted."""
    # Setup Node Keys
    ikm = secrets.token_bytes(32)
    storage_keypair = SUITE.kem.derive_key_pair(ikm)
    priv_key = storage_keypair.private_key
    pub_key = storage_keypair.public_key

    # Client Encapsulation
    plaintext_request = b"simulated-inner-bhttp-request"
    hdr = struct.pack("!BHHH", 1, SUITE.kem.id.value, SUITE.kdf.id.value, SUITE.aead.id.value)
    info = b"message/bhttp request\x00" + hdr
    enc, sender_ctx = SUITE.create_sender_context(pub_key, info=info)
    ct = sender_ctx.seal(plaintext_request)
    encapsulated_request = hdr + enc + ct

    # Upstream Gateway Mock (Decapsulates request, seals response)
    def gateway_handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        server_enc = body[7:39]
        server_ct = body[39:]
        recipient_ctx = SUITE.create_recipient_context(
            server_enc, priv_key, info=b"message/bhttp request\x00" + body[:7]
        )
        decapsulated_inner = recipient_ctx.open(server_ct)
        assert decapsulated_inner == plaintext_request

        inner_response = b"simulated-inner-bhttp-response"
        nn = SUITE.aead.nonce_size
        nk = SUITE.aead.key_size
        secret_len = max(nn, nk)
        secret = recipient_ctx.export(b"message/bhttp response", secret_len)
        resp_nonce = secrets.token_bytes(secret_len)
        salt = server_enc + resp_nonce
        prk = SUITE.kdf.extract(salt, secret)
        aead_key = SUITE.kdf.expand(prk, b"message/bhttp response\x00key", nk)
        aead_nonce = SUITE.kdf.expand(prk, b"message/bhttp response\x00nonce", nn)
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        cipher = AESGCM(aead_key)
        enc_res = resp_nonce + cipher.encrypt(aead_nonce, inner_response, b"")

        return httpx.Response(
            status_code=200,
            content=enc_res,
            headers={"content-type": "message/ohttp-res"},
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(gateway_handler))
    test_app.dependency_overrides[get_http_client] = lambda: mock_client

    try:
        # Dispatch through Relay
        relay_response = await client.post(
            "/relay",
            content=encapsulated_request,
            headers={
                "content-type": "message/ohttp-req",
                "Target-URI": "http://storage.internal/ohttp",
            },
        )

        assert relay_response.status_code == status.HTTP_200_OK
        assert relay_response.headers["content-type"] == "message/ohttp-res"

        # Client Decapsulation of Response
        enc_resp = relay_response.content
        nn = SUITE.aead.nonce_size
        nk = SUITE.aead.key_size
        secret_len = max(nn, nk)
        response_nonce = enc_resp[:secret_len]
        resp_ct = enc_resp[secret_len:]
        secret = sender_ctx.export(b"message/bhttp response", secret_len)
        salt = enc + response_nonce
        prk = SUITE.kdf.extract(salt, secret)
        aead_key = SUITE.kdf.expand(prk, b"message/bhttp response\x00key", nk)
        aead_nonce = SUITE.kdf.expand(prk, b"message/bhttp response\x00nonce", nn)
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        cipher = AESGCM(aead_key)
        decapsulated_response = cipher.decrypt(aead_nonce, resp_ct, b"")

        assert decapsulated_response == b"simulated-inner-bhttp-response"
    finally:
        test_app.dependency_overrides.clear()
