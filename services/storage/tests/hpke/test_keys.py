import os
import stat

import pytest

from src.config import settings
from src.hpke.keys import SUITE, load_or_generate_node_keys


@pytest.fixture(autouse=True)
def mock_key_dir(tmp_path, monkeypatch):
    """Isolate key directory to a temporary path for each test."""
    temp_dir = tmp_path / "keys"
    monkeypatch.setattr(settings, "HPKE_KEY_DIR", str(temp_dir))
    return temp_dir


def test_generate_fresh_keys_when_missing(mock_key_dir):
    """Verify keys are created, written to disk, and have restricted permissions."""
    priv_bytes, pub_bytes = load_or_generate_node_keys()

    # DHKEM(X25519) keys are 32 bytes each
    assert len(priv_bytes) == 32
    assert len(pub_bytes) == 32

    priv_file = mock_key_dir / "private.key"
    pub_file = mock_key_dir / "public.key"
    assert priv_file.is_file()
    assert pub_file.is_file()
    assert priv_file.read_bytes() == priv_bytes
    assert pub_file.read_bytes() == pub_bytes

    # Ensure POSIX file permissions: 0o600 for private, 0o644 for public
    if os.name == "posix":
        assert stat.S_IMODE(priv_file.stat().st_mode) == 0o600
        assert stat.S_IMODE(pub_file.stat().st_mode) == 0o644


def test_load_existing_keys_is_idempotent(mock_key_dir):
    """Verify existing key files are preserved and reloaded without overwriting."""
    mock_key_dir.mkdir(parents=True, exist_ok=True)
    seeded_priv = b"\x01" * 32
    seeded_pub = b"\x02" * 32

    (mock_key_dir / "private.key").write_bytes(seeded_priv)
    (mock_key_dir / "public.key").write_bytes(seeded_pub)

    priv_bytes, pub_bytes = load_or_generate_node_keys()

    assert priv_bytes == seeded_priv
    assert pub_bytes == seeded_pub


def test_generated_keys_cryptographic_roundtrip():
    """Verify the generated keys can successfully seal and open an HPKE payload."""
    priv_bytes, pub_bytes = load_or_generate_node_keys()

    private_key = SUITE.kem.deserialize_private_key(priv_bytes)
    public_key = SUITE.kem.deserialize_public_key(pub_bytes)

    plaintext = b"super-secret-node-payload"
    enc, sender = SUITE.create_sender_context(public_key)
    ciphertext = sender.seal(plaintext)

    recipient = SUITE.create_recipient_context(enc, private_key)
    decrypted = recipient.open(ciphertext)

    assert decrypted == plaintext
