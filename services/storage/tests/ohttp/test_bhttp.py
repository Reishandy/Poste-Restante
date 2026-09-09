import io

import pytest

from src.ohttp.bhttp import (
    decode_bhttp_request,
    decode_varint,
    encode_bhttp_response,
    encode_varint,
)


@pytest.mark.parametrize(
    "val, expected_len",
    [
        (0, 1),
        (63, 1),
        (64, 2),
        (16383, 2),
        (16384, 4),
        (1073741823, 4),
        (1073741824, 8),
        ((1 << 62) - 1, 8),
    ],
)
def test_varint_roundtrip(val: int, expected_len: int):
    encoded = encode_varint(val)
    assert len(encoded) == expected_len
    buf = io.BytesIO(encoded)
    decoded = decode_varint(buf)
    assert decoded == val
    assert buf.tell() == expected_len


def test_varint_overflow():
    with pytest.raises(ValueError, match="exceeds 62 bits"):
        encode_varint(1 << 62)


@pytest.mark.parametrize(
    "truncated_bytes",
    [
        b"",
        b"\x40",  # 2-byte prefix, missing 1 byte
        b"\x80\x01",  # 4-byte prefix, missing 2 bytes
        b"\xc0\x01\x02\x03",  # 8-byte prefix, missing 4 bytes
    ],
)
def test_varint_premature_eof(truncated_bytes: bytes):
    buf = io.BytesIO(truncated_bytes)
    with pytest.raises(EOFError):
        decode_varint(buf)


def test_decode_bhttp_request_known_length():
    # Construct binary request: framing(0), method, scheme, authority, path, headers, body
    out = io.BytesIO()
    out.write(encode_varint(0))  # Request framing indicator
    for field in (b"POST", b"https", b"mailbox.local", b"/blob/msg-123"):
        out.write(encode_varint(len(field)) + field)

    # Headers: Content-Type and X-Custom
    h_buf = io.BytesIO()
    for k, v in [(b"content-type", b"application/json"), (b"x-ownership-token", b"secret-token")]:
        h_buf.write(encode_varint(len(k)) + k)
        h_buf.write(encode_varint(len(v)) + v)
    h_data = h_buf.getvalue()

    out.write(encode_varint(len(h_data)) + h_data)
    body = b'{"content": "encrypted-payload"}'
    out.write(encode_varint(len(body)) + body)

    parsed = decode_bhttp_request(out.getvalue())
    assert parsed.method == "POST"
    assert parsed.scheme == "https"
    assert parsed.authority == "mailbox.local"
    assert parsed.path == "/blob/msg-123"
    assert parsed.headers["content-type"] == "application/json"
    assert parsed.headers["x-ownership-token"] == "secret-token"
    assert parsed.body == body


def test_decode_bhttp_request_invalid_framing():
    out = io.BytesIO()
    out.write(encode_varint(1))  # 1 is response framing, invalid for request
    out.write(b"\x03GET\x04http\x00\x01/")
    with pytest.raises(ValueError, match="Unsupported BHTTP framing indicator"):
        decode_bhttp_request(out.getvalue())


def test_encode_bhttp_response_filters_hop_by_hop_headers():
    headers = {
        "content-type": "application/json",
        "connection": "close",
        "keep-alive": "timeout=5",
        ":status": "200",
    }
    encoded = encode_bhttp_response(200, headers, b'{"status":"ok"}')

    buf = io.BytesIO(encoded)
    assert decode_varint(buf) == 1  # Known-length response framing indicator
    assert decode_varint(buf) == 200  # Status code

    h_len = decode_varint(buf)
    h_bytes = buf.read(h_len)
    assert b"connection" not in h_bytes.lower()
    assert b"keep-alive" not in h_bytes.lower()
    assert b":status" not in h_bytes
    assert b"content-type" in h_bytes
