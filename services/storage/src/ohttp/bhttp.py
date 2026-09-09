import io
from dataclasses import dataclass, field


def encode_varint(v: int) -> bytes:
    if v < (1 << 6):
        return bytes([v])
    elif v < (1 << 14):
        return bytes([(v >> 8) | 0x40, v & 0xFF])
    elif v < (1 << 30):
        return bytes(
            [(v >> 24) | 0x80, (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF]
        )
    elif v < (1 << 62):
        b = [(v >> 56) | 0xC0]
        for i in range(6, -1, -1):
            b.append((v >> (i * 8)) & 0xFF)
        return bytes(b)
    raise ValueError(f"Varint value {v} exceeds 62 bits")


def decode_varint(buf: io.BytesIO) -> int:
    first = buf.read(1)
    if not first:
        raise EOFError("Unexpected EOF while reading varint")
    b0 = first[0]
    prefix = b0 >> 6
    val = b0 & 0x3F
    if prefix == 0:
        return val
    elif prefix == 1:
        rest = buf.read(1)
        if len(rest) < 1:
            raise EOFError()
        return (val << 8) | rest[0]
    elif prefix == 2:
        rest = buf.read(3)
        if len(rest) < 3:
            raise EOFError()
        return (val << 24) | (rest[0] << 16) | (rest[1] << 8) | rest[2]
    else:
        rest = buf.read(7)
        if len(rest) < 7:
            raise EOFError()
        res = val
        for b in rest:
            res = (res << 8) | b
        return res


def _read_length_prefixed(buf: io.BytesIO) -> bytes:
    length = decode_varint(buf)
    data = buf.read(length)
    if len(data) < length:
        raise EOFError("Premature EOF reading length-prefixed bytes")
    return data


@dataclass
class BHTTPRequest:
    method: str
    scheme: str
    authority: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""


def decode_bhttp_request(raw_bhttp: bytes) -> BHTTPRequest:
    buf = io.BytesIO(raw_bhttp)
    framing_indicator = decode_varint(buf)
    if framing_indicator != 0:
        raise ValueError(
            f"Unsupported BHTTP framing indicator: {framing_indicator}"
        )

    method = _read_length_prefixed(buf).decode("ascii")
    scheme = _read_length_prefixed(buf).decode("ascii")
    authority = _read_length_prefixed(buf).decode("ascii")
    path = _read_length_prefixed(buf).decode("ascii")

    headers_length = decode_varint(buf)
    headers_bytes = buf.read(headers_length)
    headers_buf = io.BytesIO(headers_bytes)
    headers: dict[str, str] = {}
    while headers_buf.tell() < headers_length:
        name = _read_length_prefixed(headers_buf).decode("latin1").lower()
        val = _read_length_prefixed(headers_buf).decode("latin1")
        headers[name] = val

    body = b""
    try:
        body_length = decode_varint(buf)
        body = buf.read(body_length)
    except EOFError:
        pass

    return BHTTPRequest(
        method=method,
        scheme=scheme,
        authority=authority,
        path=path,
        headers=headers,
        body=body,
    )


def encode_bhttp_response(
        status_code: int, headers: dict[str, str], body: bytes
) -> bytes:
    out = io.BytesIO()
    out.write(encode_varint(1))  # Known-Length Response indicator
    out.write(encode_varint(status_code))

    h_buf = io.BytesIO()
    for name, val in headers.items():
        if name.startswith(":") or name in {"connection", "keep-alive"}:
            continue
        encoded_name = name.lower().encode("latin1")
        encoded_val = val.encode("latin1")
        h_buf.write(encode_varint(len(encoded_name)) + encoded_name)
        h_buf.write(encode_varint(len(encoded_val)) + encoded_val)

    h_data = h_buf.getvalue()
    out.write(encode_varint(len(h_data)) + h_data)
    out.write(encode_varint(len(body)) + body)
    out.write(encode_varint(0))  # Empty trailer section
    return out.getvalue()
