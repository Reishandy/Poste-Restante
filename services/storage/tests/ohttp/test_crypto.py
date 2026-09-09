import struct

import pytest

from src.ohttp.crypto import (
    OHTTP_KEY_ID,
    _get_aead_cipher,
    decapsulate_request,
    encapsulate_response,
)
from src.ohttp.keys import SUITE, load_or_generate_node_keys


def _client_encapsulate(
        bhttp_req: bytes, pub_bytes: bytes, key_id: int = OHTTP_KEY_ID
):
    """Simulates an RFC 9458 client encapsulating a request."""
    pub_key = SUITE.kem.deserialize_public_key(pub_bytes)
    hdr = struct.pack(
        "!BHHH",
        key_id,
        SUITE.kem.id.value,
        SUITE.kdf.id.value,
        SUITE.aead.id.value,
    )
    info = b"message/bhttp request\x00" + hdr
    enc, sender_ctx = SUITE.create_sender_context(pub_key, info=info)
    ct = sender_ctx.seal(bhttp_req)
    return hdr + enc + ct, sender_ctx, enc


def _client_decapsulate_response(
        enc_resp: bytes, sender_ctx, enc: bytes
) -> bytes:
    """Simulates an RFC 9458 client decapsulating a server response."""
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


def test_ohttp_crypto_end_to_end_roundtrip():
    priv_bytes, pub_bytes = load_or_generate_node_keys()
    priv_key = SUITE.kem.deserialize_private_key(priv_bytes)

    plaintext_request = b"simulated-bhttp-request"
    enc_request, sender_ctx, enc = _client_encapsulate(plaintext_request, pub_bytes)

    decapsulated_req, recipient_ctx, server_enc = decapsulate_request(
        enc_request, priv_key
    )
    assert decapsulated_req == plaintext_request
    assert server_enc == enc

    plaintext_response = b"simulated-bhttp-response"
    enc_response = encapsulate_response(
        plaintext_response, recipient_ctx, server_enc
    )

    decapsulated_res = _client_decapsulate_response(
        enc_response, sender_ctx, enc
    )
    assert decapsulated_res == plaintext_response


def test_decapsulate_request_payload_too_short():
    priv_bytes, _ = load_or_generate_node_keys()
    priv_key = SUITE.kem.deserialize_private_key(priv_bytes)

    with pytest.raises(ValueError, match="payload too short"):
        decapsulate_request(b"\x01" * 54, priv_key)


@pytest.mark.parametrize(
    "key_id, kem_id, kdf_id, aead_id",
    [
        (99, SUITE.kem.id.value, SUITE.kdf.id.value, SUITE.aead.id.value),
        (OHTTP_KEY_ID, 0xFFFF, SUITE.kdf.id.value, SUITE.aead.id.value),
        (OHTTP_KEY_ID, SUITE.kem.id.value, 0xFFFF, SUITE.aead.id.value),
        (OHTTP_KEY_ID, SUITE.kem.id.value, SUITE.kdf.id.value, 0xFFFF),
    ],
)
def test_decapsulate_request_mismatched_ciphersuite(
        key_id, kem_id, kdf_id, aead_id
):
    priv_bytes, _ = load_or_generate_node_keys()
    priv_key = SUITE.kem.deserialize_private_key(priv_bytes)
    hdr = struct.pack("!BHHH", key_id, kem_id, kdf_id, aead_id)
    bogus_payload = hdr + b"\x00" * (32 + 16)

    with pytest.raises(ValueError, match="Unsupported or mismatched"):
        decapsulate_request(bogus_payload, priv_key)


def test_decapsulate_tampered_ciphertext_fails():
    priv_bytes, pub_bytes = load_or_generate_node_keys()
    priv_key = SUITE.kem.deserialize_private_key(priv_bytes)

    enc_req, _, _ = _client_encapsulate(b"valid payload", pub_bytes)
    tampered_req = enc_req[:-1] + bytes([enc_req[-1] ^ 0x01])

    with pytest.raises(Exception):
        decapsulate_request(tampered_req, priv_key)
