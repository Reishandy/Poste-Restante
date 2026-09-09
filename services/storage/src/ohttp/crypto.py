import secrets
import struct

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from pyhpke import AEADId, ContextInterface

from src.ohttp.keys import SUITE

OHTTP_KEY_ID = 1


def _get_aead_cipher(aead_id: AEADId, key: bytes):
    """Instantiates a raw AEAD primitive from cryptography for response encap/decap."""
    if aead_id in (AEADId.AES128_GCM, AEADId.AES256_GCM):
        return AESGCM(key)
    elif aead_id == AEADId.CHACHA20_POLY1305:
        return ChaCha20Poly1305(key)
    raise ValueError(f"Unsupported AEAD algorithm: {aead_id}")


def decapsulate_request(
        enc_request: bytes, private_key
) -> tuple[bytes, ContextInterface, bytes]:
    """
    Decapsulates RFC 9458 OHTTP request.
    Header: key_id(1) || kem_id(2) || kdf_id(2) || aead_id(2) || enc(32) || ct
    """
    if len(enc_request) < 7 + 32 + 16:
        raise ValueError("Encapsulated request payload too short")

    key_id, kem_id, kdf_id, aead_id = struct.unpack("!BHHH", enc_request[:7])
    if (
            key_id != OHTTP_KEY_ID
            or kem_id != SUITE.kem.id.value
            or kdf_id != SUITE.kdf.id.value
            or aead_id != SUITE.aead.id.value
    ):
        raise ValueError("Unsupported or mismatched OHTTP key/cipher parameters")

    enc = enc_request[7:39]
    ct = enc_request[39:]

    info = b"message/bhttp request\x00" + enc_request[:7]
    recipient_ctx = SUITE.create_recipient_context(enc, private_key, info=info)
    bhttp_bytes = recipient_ctx.open(ct)
    return bhttp_bytes, recipient_ctx, enc


def encapsulate_response(
        bhttp_response: bytes, recipient_ctx: ContextInterface, enc: bytes
) -> bytes:
    """
    Encapsulates RFC 9458 OHTTP response using the shared HPKE context.
    Returns: response_nonce || ciphertext
    """
    nn = SUITE.aead.nonce_size
    nk = SUITE.aead.key_size
    secret_len = max(nn, nk)

    secret = recipient_ctx.export(b"message/bhttp response", secret_len)
    response_nonce = secrets.token_bytes(secret_len)

    salt = enc + response_nonce
    prk = SUITE.kdf.extract(salt, secret)
    aead_key = SUITE.kdf.expand(prk, b"message/bhttp response\x00key", nk)
    aead_nonce = SUITE.kdf.expand(prk, b"message/bhttp response\x00nonce", nn)

    cipher = _get_aead_cipher(SUITE.aead.id, aead_key)
    ct = cipher.encrypt(aead_nonce, bhttp_response, b"")
    return response_nonce + ct
