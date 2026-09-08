from pydantic import BaseModel, Field

from src.schemas import Response


class BlobStore(BaseModel):
    content: str = Field(..., description="The content of the blob.", examples=["U2FsdGVkX1+osqDU1dTNDbhqegX2r9yTFIqY1oCywhI="])


class BlobResponse(Response):
    content: str = Field(..., description="The content of the blob.", examples=["U2FsdGVkX1+osqDU1dTNDbhqegX2r9yTFIqY1oCywhI="])


class BadRequest(Response):
    detail: str = Field(
        default="Bad Request",
        description="The error detail",
        examples=["Bad Request"],
    )
