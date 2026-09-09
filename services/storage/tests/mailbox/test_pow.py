import time

import pytest
from src.mailbox.dependenies import solve_pow
from starlette import status

from src.config import settings


@pytest.fixture(autouse=True)
def lower_pow_difficulty(monkeypatch):
    """Lower difficulty during test runs to compute nonces in sub-milliseconds."""
    monkeypatch.setattr(settings, "POW_DIFFICULTY_BITS", 8)


async def test_put_mailbox_with_valid_pow_succeeds(client):
    mailbox_id = "pow-valid-mailbox"
    nonce = solve_pow(mailbox_id)
    payload = {"content": "payload", "token": "secret-token"}

    response = await client.put(
        f"/mailbox/{mailbox_id}",
        json=payload,
        headers={"X-PoW-Nonce": nonce},
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["detail"] == "ok"


async def test_put_mailbox_missing_pow_header_returns_422(client):
    mailbox_id = "pow-missing-header-mailbox"
    payload = {"content": "payload", "token": "secret-token"}

    response = await client.put(f"/mailbox/{mailbox_id}", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_put_mailbox_invalid_nonce_returns_400(client):
    mailbox_id = "pow-invalid-nonce-mailbox"
    payload = {"content": "payload", "token": "secret-token"}

    response = await client.put(
        f"/mailbox/{mailbox_id}",
        json=payload,
        headers={"X-PoW-Nonce": "bogus-nonce-12345"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid or expired proof of work"


async def test_put_mailbox_rejects_nonce_mined_for_different_mailbox(client):
    target_mailbox_id = "target-mailbox-001"
    other_mailbox_id = "other-mailbox-002"
    nonce_for_other = solve_pow(other_mailbox_id)
    payload = {"content": "payload", "token": "secret-token"}

    response = await client.put(
        f"/mailbox/{target_mailbox_id}",
        json=payload,
        headers={"X-PoW-Nonce": nonce_for_other},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid or expired proof of work"


@pytest.mark.parametrize("epoch_delta", [-1, 1])
async def test_put_mailbox_accepts_tolerated_epoch_drift(client, epoch_delta):
    mailbox_id = f"pow-drift-{epoch_delta}-mailbox"
    current_epoch = int(time.time() // settings.POW_EPOCH_WINDOW_SECONDS)
    drifted_epoch = current_epoch + epoch_delta

    nonce = solve_pow(mailbox_id, epoch=drifted_epoch)
    payload = {"content": "payload", "token": "secret-token"}

    response = await client.put(
        f"/mailbox/{mailbox_id}",
        json=payload,
        headers={"X-PoW-Nonce": nonce},
    )
    assert response.status_code == status.HTTP_201_CREATED


async def test_put_mailbox_rejects_expired_epoch(client):
    mailbox_id = "pow-expired-mailbox"
    current_epoch = int(time.time() // settings.POW_EPOCH_WINDOW_SECONDS)
    expired_epoch = current_epoch - 2  # Outside [-1, 0, 1] tolerance

    nonce = solve_pow(mailbox_id, epoch=expired_epoch)
    payload = {"content": "payload", "token": "secret-token"}

    response = await client.put(
        f"/mailbox/{mailbox_id}",
        json=payload,
        headers={"X-PoW-Nonce": nonce},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid or expired proof of work"


async def test_get_and_delete_do_not_require_pow_header(client):
    mailbox_id = "pow-bypass-read-delete"
    nonce = solve_pow(mailbox_id)
    token = "owner-token-pow"

    # Create mailbox first with valid PoW
    await client.put(
        f"/mailbox/{mailbox_id}",
        json={"content": "readable", "token": token},
        headers={"X-PoW-Nonce": nonce},
    )

    # GET must succeed without X-PoW-Nonce
    get_res = await client.get(
        f"/mailbox/{mailbox_id}",
        headers={"X-Ownership-Token": token},
    )
    assert get_res.status_code == status.HTTP_200_OK

    # DELETE must succeed without X-PoW-Nonce
    del_res = await client.delete(
        f"/mailbox/{mailbox_id}",
        headers={"X-Ownership-Token": token},
    )
    assert del_res.status_code == status.HTTP_200_OK
