import hashlib
import secrets
import time

from fastapi import Header, HTTPException, Request
from starlette import status

from src.config import settings


def verify_internal_dispatch(
        request: Request,
        x_internal_dispatch: str = Header(
            default="",
            alias="X-Internal-Dispatch",
            include_in_schema=False,
        ),
):
    expected = getattr(request.app.state, "internal_dispatch_token", None)
    if not expected or not secrets.compare_digest(x_internal_dispatch, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct HTTP access forbidden. Access via OHTTP gateway only.",
        )


def count_leading_zero_bits(digest: bytes) -> int:
    """Calculates continuous leading zero bits in a digest."""
    zeros = 0
    for byte in digest:
        if byte == 0:
            zeros += 8
        else:
            zeros += 8 - byte.bit_length()
            break
    return zeros


def is_valid_pow(mailbox_id: str, nonce: str, epoch: int, difficulty: int) -> bool:
    """Checks whether sha256(epoch:mailbox_id:nonce) meets the difficulty target."""
    challenge = f"{epoch}:{mailbox_id}:{nonce}".encode("utf-8")
    digest = hashlib.sha256(challenge).digest()
    return count_leading_zero_bits(digest) >= difficulty


def solve_pow(
        mailbox_id: str,
        epoch: int | None = None,
        difficulty: int | None = None,
) -> str:
    """Mines a valid nonce for a given mailbox ID and epoch (used by tests and client routines)."""
    if epoch is None:
        epoch = int(time.time() // settings.POW_EPOCH_WINDOW_SECONDS)
    if difficulty is None:
        difficulty = settings.POW_DIFFICULTY_BITS

    nonce = 0
    while True:
        candidate = str(nonce)
        if is_valid_pow(mailbox_id, candidate, epoch, difficulty):
            return candidate
        nonce += 1


def verify_pow(
        mailbox_id: str,
        x_pow_nonce: str = Header(
            ...,
            alias="X-PoW-Nonce",
            description="Proof of work nonce meeting difficulty requirement",
        ),
) -> None:
    """
    Validates proof-of-work on mailbox writes before touching the database.
    Tolerates +/- 1 epoch window to account for client network lag and clock drift.
    """
    if settings.POW_DIFFICULTY_BITS <= 0:
        return

    current_epoch = int(time.time() // settings.POW_EPOCH_WINDOW_SECONDS)
    valid = any(
        is_valid_pow(
            mailbox_id=mailbox_id,
            nonce=x_pow_nonce,
            epoch=current_epoch + delta,
            difficulty=settings.POW_DIFFICULTY_BITS,
        )
        for delta in (0, -1, 1)
    )

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired proof of work",
        )
