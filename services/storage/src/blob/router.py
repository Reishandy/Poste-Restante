from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status

from src.blob import service
from src.blob.schemas import BlobResponse, BlobStore, BadRequest
from src.database import get_database
from src.schemas import Response

router = APIRouter(prefix="/blob", tags=["Blob Storage"])


@router.get(
    "/{blob_id}",
    summary="Get a blob",
    description="Endpoint to get a blob given its id",
    response_model=BlobResponse,
    responses={
        status.HTTP_200_OK: {
            "model": BlobResponse,
            "description": "Return a blob",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": BadRequest,
            "description": "Bad Request",
        }
    },
)
async def get_blob(
        blob_id: str,
        db: AsyncIOMotorDatabase = Depends(get_database)
) -> BlobResponse:
    # TODO: Return 400 for both id not found or failed auth
    result = await service.get_blob(db, blob_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bad request",
        )

    return BlobResponse(
        detail="ok",
        content=result
    )


@router.put(
    "/{blob_id}",
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
        }
    },
)
async def store_blob(
        blob_id: str,
        payload: BlobStore,
        db: AsyncIOMotorDatabase = Depends(get_database)
) -> Response:
    # TODO: Durable write?
    success = await service.store_blob(db, blob_id, payload.content)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bad request"
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
        }
    },
)
async def delete_blob(
        blob_id: str,
        db: AsyncIOMotorDatabase = Depends(get_database)
) -> Response:
    # TODO: Return 400 for both id not found or failed auth
    success = await service.delete_blob(db, blob_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bad request"
        )

    return Response(detail="ok")
