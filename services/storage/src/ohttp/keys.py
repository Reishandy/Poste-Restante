import secrets
from pathlib import Path

from pyhpke import AEADId, CipherSuite, KDFId, KEMId

from src.config import settings

SUITE = CipherSuite.new(
    KEMId.DHKEM_X25519_HKDF_SHA256, KDFId.HKDF_SHA256, AEADId.AES256_GCM
)


def load_or_generate_node_keys() -> tuple[bytes, bytes]:
    """
    Generates a fresh keypair only if none exists yet on disk (first boot).

    :returns: (private_key_bytes, public_key_bytes)
    """
    key_dir = Path(settings.HPKE_KEY_DIR)
    key_dir.mkdir(parents=True, exist_ok=True)

    priv_path = key_dir / "private.key"
    pub_path = key_dir / "public.key"

    if priv_path.exists() and pub_path.exists():
        return priv_path.read_bytes(), pub_path.read_bytes()

    ikm = secrets.token_bytes(32)
    keypair = SUITE.kem.derive_key_pair(ikm)

    priv_bytes = keypair.private_key.to_private_bytes()
    pub_bytes = keypair.public_key.to_public_bytes()

    priv_path.write_bytes(priv_bytes)
    priv_path.chmod(0o600)
    pub_path.write_bytes(pub_bytes)
    pub_path.chmod(0o644)

    return priv_bytes, pub_bytes
