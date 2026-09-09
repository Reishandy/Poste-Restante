import io
import json
import struct

from starlette import status

from src.ohttp.bhttp import decode_varint, encode_varint
from src.ohttp.crypto import OHTTP_KEY_ID, _get_aead_cipher
from src.ohttp.keys import SUITE


def _build_bhttp_request(
        method: str, path: str, headers: dict[str, str], body: bytes = b""
) -> bytes:
    """Serializes a request into Binary HTTP (RFC 9292)."""
    out = io.BytesIO()
    out.write(encode_varint(0))
    for field in (method.encode("ascii"), b"https", b"storage.internal", path.encode("ascii")):
        out.write(encode_varint(len(field)) + field)

    h_buf = io.BytesIO()
    for k, v in headers.items():
        kb, vb = k.lower().encode("latin1"), v.encode("latin1")
        h_buf.write(encode_varint(len(kb)) + kb)
        h_buf.write(encode_varint(len(vb)) + vb)
    h_bytes = h_buf.getvalue()

    out.write(encode_varint(len(h_bytes)) + h_bytes)
    out.write(encode_varint(len(body)) + body)
    return out.getvalue()


def _decode_bhttp_response(raw_bhttp: bytes) -> tuple[int, dict[str, str], bytes]:
    """Decodes a Binary HTTP response."""
    buf = io.BytesIO(raw_bhttp)
    framing = decode_varint(buf)
    assert framing == 1, f"Expected known-length response framing, got {framing}"
    status_code = decode_varint(buf)

    h_len = decode_varint(buf)
    h_data = buf.read(h_len)
    h_buf = io.BytesIO(h_data)
    headers = {}
    while h_buf.tell() < h_len:
        k_len = decode_varint(h_buf)
        k = h_buf.read(k_len).decode("latin1")
        v_len = decode_varint(h_buf)
        v = h_buf.read(v_len).decode("latin1")
        headers[k] = v

    body_len = decode_varint(buf)
    body = buf.read(body_len)
    return status_code, headers, body


def _encapsulate_ohttp_request(bhttp_req: bytes, pub_key):
    hdr = struct.pack(
        "!BHHH",
        OHTTP_KEY_ID,
        SUITE.kem.id.value,
        SUITE.kdf.id.value,
        SUITE.aead.id.value,
    )
    info = b"message/bhttp request\x00" + hdr
    enc, sender_ctx = SUITE.create_sender_context(pub_key, info=info)
    ct = sender_ctx.seal(bhttp_req)
    return hdr + enc + ct, sender_ctx, enc


def _decapsulate_ohttp_response(enc_resp: bytes, sender_ctx, enc: bytes) -> bytes:
    nn = SUITE.aead.nonce_size
    nk = SUITE.aead.key_size
    secret_len = max(nn, nk)

    response_nonce = enc_resp[:secret_len]
    ct = enc_resp[secret_len:]

    secret = sender_ctx.export(b"message/bhttp response", secret_len)
    salt = enc + response_nonce
    prk = SUITE.kdf.extract(salt, secret)
    aead_key = SUITE.kdf.expand(prk, b"message/bhttp response\x00key", nk)
    aead_nonce = SUITE.kdf.expand(prk, b"message/bhttp response\x00nonce", nn)

    cipher = _get_aead_cipher(SUITE.aead.id, aead_key)
    return cipher.decrypt(aead_nonce, ct, b"")


async def test_ohttp_gateway_full_blob_lifecycle(external_client, test_app):
    """End-to-end: client encapsulates PUT, GET, DELETE through /ohttp[cite: 1]."""
    pub_key = test_app.state.hpke_public_key
    blob_id = "ohttp-blob-001"
    token = "owner-token-secret"
    content = "encapsulated-durable-data"

    put_body = json.dumps({"content": content, "token": token}).encode()
    bhttp_put = _build_bhttp_request(
        method="PUT",
        path=f"/blob/{blob_id}",
        headers={"content-type": "application/json"},
        body=put_body,
    )
    enc_req, sender_ctx, enc = _encapsulate_ohttp_request(bhttp_put, pub_key)

    res = await external_client.post(
        "/ohttp",
        content=enc_req,
        headers={"content-type": "message/ohttp-req"},
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.headers["content-type"] == "message/ohttp-res"

    dec_res_bytes = _decapsulate_ohttp_response(res.content, sender_ctx, enc)
    inner_status, _, inner_body = _decode_bhttp_response(dec_res_bytes)
    assert inner_status == status.HTTP_201_CREATED
    assert json.loads(inner_body)["detail"] == "ok"

    bhttp_get = _build_bhttp_request(
        method="GET",
        path=f"/blob/{blob_id}",
        headers={"x-ownership-token": token},
    )
    enc_req, sender_ctx, enc = _encapsulate_ohttp_request(bhttp_get, pub_key)

    res = await external_client.post(
        "/ohttp",
        content=enc_req,
        headers={"content-type": "message/ohttp-req"},
    )
    assert res.status_code == status.HTTP_200_OK

    dec_res_bytes = _decapsulate_ohttp_response(res.content, sender_ctx, enc)
    inner_status, _, inner_body = _decode_bhttp_response(dec_res_bytes)
    assert inner_status == status.HTTP_200_OK
    assert json.loads(inner_body)["content"] == content

    bhttp_del = _build_bhttp_request(
        method="DELETE",
        path=f"/blob/{blob_id}",
        headers={"x-ownership-token": token},
    )
    enc_req, sender_ctx, enc = _encapsulate_ohttp_request(bhttp_del, pub_key)

    res = await external_client.post(
        "/ohttp",
        content=enc_req,
        headers={"content-type": "message/ohttp-req"},
    )
    assert res.status_code == status.HTTP_200_OK

    dec_res_bytes = _decapsulate_ohttp_response(res.content, sender_ctx, enc)
    inner_status, _, inner_body = _decode_bhttp_response(dec_res_bytes)
    assert inner_status == status.HTTP_200_OK
    assert json.loads(inner_body)["detail"] == "ok"


async def test_ohttp_gateway_corrupted_envelope_returns_400(external_client):
    """Corrupted outer HPKE request returns HTTP 400 immediately[cite: 1]."""
    res = await external_client.post(
        "/ohttp",
        content=b"not-a-valid-ohttp-envelope",
        headers={"content-type": "message/ohttp-req"},
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Decapsulation failed" in res.json()["detail"]


async def test_ohttp_gateway_propagates_inner_client_errors(
        external_client, test_app
):
    """Inner 400 Bad Request is preserved and encapsulated inside an outer 200 OK[cite: 1]."""
    pub_key = test_app.state.hpke_public_key

    bhttp_get = _build_bhttp_request(
        method="GET",
        path="/blob/non-existent-blob",
        headers={"x-ownership-token": "any-token"},
    )
    enc_req, sender_ctx, enc = _encapsulate_ohttp_request(bhttp_get, pub_key)

    res = await external_client.post(
        "/ohttp",
        content=enc_req,
        headers={"content-type": "message/ohttp-req"},
    )
    assert res.status_code == status.HTTP_200_OK

    dec_res_bytes = _decapsulate_ohttp_response(res.content, sender_ctx, enc)
    inner_status, _, inner_body = _decode_bhttp_response(dec_res_bytes)
    assert inner_status == status.HTTP_400_BAD_REQUEST
    assert json.loads(inner_body)["detail"] == "Bad Request"
