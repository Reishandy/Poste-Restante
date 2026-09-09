from fastapi import APIRouter, Depends, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status

from src.database import get_database
from src.mailbox import service
from src.mailbox.dependenies import verify_internal_dispatch, verify_pow
from src.mailbox.schemas import BadRequest, MailboxResponse, MailboxStore
from src.schemas import Response

router = APIRouter(
    prefix="/mailbox",
    tags=["Mailbox Storage (Encapsulated)"],
    responses={
        403: {"description": "Returned if called outside an OHTTP encapsulation"}
    },
    dependencies=[Depends(verify_internal_dispatch)],
)


@router.get(
    "/{mailbox_id}",
    summary="Retrieve Mailbox",
    description="""
    Fetches ciphertext using the bearer `X-Ownership-Token`.

    * Does not delete content upon reading.
    * Deliberately returns identical `400 Bad Request` responses for both invalid tokens and non-existent/expired IDs to prevent key enumeration.
    """,
    response_model=MailboxResponse,
    responses={
        status.HTTP_200_OK: {
            "model": MailboxResponse,
            "description": "Return a mailbox",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": BadRequest,
            "description": "Bad Request",
        },
    },
)
async def get_mailbox(
        mailbox_id: str,
        x_ownership_token: str = Header(
            ...,
            alias="X-Ownership-Token",
            description="Proof of ownership token",
        ),
        db: AsyncIOMotorDatabase = Depends(get_database),
) -> MailboxResponse:
    result = await service.get_mailbox(db, mailbox_id, x_ownership_token)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad Request",
        )

    return MailboxResponse(detail="ok", content=result)


@router.put(
    "/{mailbox_id}",
    summary="Create Mailbox (Write-Once)",
    description="""
    Stores an encrypted payload under a unique `mailbox_id`.
    
    * Requires valid `X-PoW-Nonce` matching `sha256(epoch:mailbox_id:nonce)`.
    * Duplicate writes to an existing `mailbox_id` return `400 Bad Request`.
    * The token provided in the body is required for subsequent read/delete operations.
    """,
    status_code=status.HTTP_201_CREATED,
    response_model=Response,
    dependencies=[Depends(verify_pow)],
    responses={
        status.HTTP_201_CREATED: {
            "model": Response,
            "description": "Mailbox stored",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": BadRequest,
            "description": "Bad request",
        },
    },
)
async def store_mailbox(
        mailbox_id: str,
        payload: MailboxStore,
        db: AsyncIOMotorDatabase = Depends(get_database),
) -> Response:
    success = await service.store_mailbox(
        db, mailbox_id, payload.content, payload.token
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request"
        )

    return Response(detail="ok")


@router.delete(
    "/{mailbox_id}",
    summary="Purge Mailbox",
    description="""
    Permanently removes a mailbox record from storage.

    * Requires valid `X-Ownership-Token`.
    * Idempotent: returns `200 OK` whether the mailbox existed or was already removed.
    """,
    response_model=Response,
    responses={
        status.HTTP_200_OK: {
            "model": Response,
            "description": "Mailbox deleted",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": BadRequest,
            "description": "Bad Request",
        },
    },
)
async def delete_mailbox(
        mailbox_id: str,
        x_ownership_token: str = Header(
            ...,
            alias="X-Ownership-Token",
            description="Proof of ownership token",
        ),
        db: AsyncIOMotorDatabase = Depends(get_database),
) -> Response:
    success = await service.delete_mailbox(db, mailbox_id, x_ownership_token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request"
        )

    return Response(detail="ok")
