from typing import reveal_type

from fastapi import APIRouter
from starlette import status

from src.blob.schemas import BlobResponse, BlobStore, BadRequest
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
async def get_blob(blob_id: str):
    # TODO: Return 400 for both id not found or failed auth
    # TODO: Implement service to get
    return BlobResponse(content=blob_id)


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
            "description": "Bad Request",
        }
    },
)
async def store_blob(blob_id: str, payload: BlobStore):
    # TODO: Return 400 for already exists
    # TODO: Implement service to store
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
            "description": "Bad Request",
        }
    },
)
async def delete_blob(blob_id: str):
    # TODO: Return 400 for both id not found or failed auth
    # TODO: Implement service to delete
    return Response(detail="ok")