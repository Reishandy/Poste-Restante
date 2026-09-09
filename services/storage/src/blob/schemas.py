from pydantic import BaseModel, Field
from src.schemas import Response


class BlobStore(BaseModel):
    content: str = Field(
        ...,
        description="The content of the blob.",
        examples=["U2FsdGVkX1+osqDU1dTNDbhqegX2r9yTFIqY1oCywhI="],
    )
    token: str = Field(
        ...,
        description="Ownership token required to retrieve or delete this blob.",
        examples=["U2FsdGVkX186lfm0PXLFVg4fg7kQL3fY4eOmRgluwPBwQhg7GvuXxSwrtXHg9feD"],
    )


class BlobResponse(Response):
    content: str = Field(
        ...,
        description="The content of the blob.",
        examples=["U2FsdGVkX1+osqDU1dTNDbhqegX2r9yTFIqY1oCywhI="],
    )


class BadRequest(Response):
    detail: str = Field(
        default="Bad Request",
        description="The error detail",
        examples=["bad request"],
    )