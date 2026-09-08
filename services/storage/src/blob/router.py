from fastapi import APIRouter, Depends, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status

from src.blob import service
from src.blob.schemas import BadRequest, BlobResponse, BlobStore
from src.database import get_database
from src.schemas import Response

router = APIRouter(prefix="/blob", tags=["Blob Storage"])


@router.get(
    "/{blob_id}",
    summary="Get a blob",
    description="Endpoint to get a blob given its id and ownership token",
    response_model=BlobResponse,
    responses={
        status.HTTP_200_OK: {
            "model": BlobResponse,
            "description": "Return a blob",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": BadRequest,
            "description": "Bad Request",
        },
    },
)
async def get_blob(
        blob_id: str,
        x_ownership_token: str = Header(
            ...,
            alias="X-Ownership-Token",
            description="Proof of ownership token",
        ),
        db: AsyncIOMotorDatabase = Depends(get_database),
) -> BlobResponse:
    result = await service.get_blob(db, blob_id, x_ownership_token)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bad request",
        )

    return BlobResponse(detail="ok", content=result)


@router.put(
    "/{blob_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Store new blob",
    description="Endpoint to store a new blob by id",
    response_model=Response,
    responses={
        status.HTTP_201_CREATED: {
            "model": Response,
            "description": "Blob stored",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": BadRequest,
            "description": "bad request",
        },
    },
)
async def store_blob(
        blob_id: str,
        payload: BlobStore,
        db: AsyncIOMotorDatabase = Depends(get_database),
) -> Response:
    success = await service.store_blob(
        db, blob_id, payload.content, payload.token
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="bad request"
        )

    return Response(detail="ok")


@router.delete(
    "/{blob_id}",
    summary="Delete a blob",
    description="Endpoint to delete a blob",
    response_model=Response,
    responses={
        status.HTTP_200_OK: {
            "model": Response,
            "description": "Blob deleted",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": BadRequest,
            "description": "bad request",
        },
    },
)
async def delete_blob(
        blob_id: str,
        x_ownership_token: str = Header(
            ...,
            alias="X-Ownership-Token",
            description="Proof of ownership token",
        ),
        db: AsyncIOMotorDatabase = Depends(get_database),
) -> Response:
    success = await service.delete_blob(db, blob_id, x_ownership_token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="bad request"
        )

    return Response(detail="ok")
