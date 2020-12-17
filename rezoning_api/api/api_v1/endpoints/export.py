"""Filter endpoints."""
from enum import Enum
from email.utils import format_datetime

from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse

from rezoning_api.utils import s3_head, s3_get, get_hash
from rezoning_api.core.config import BUCKET
from rezoning_api.models.zone import Filters, LCOE, Weights


router = APIRouter()


class Operation(str, Enum):
    """possible export operations"""

    LCOE = "lcoe"
    SCORE = "score"


@router.post(
    "/export/{operation}/{country_id}",
    responses={201: dict(description="start export processing for a given country")},
    name="export",
)
def export(
    operation: Operation,
    country_id: str,
    weights: Weights = Depends(),
    lcoe: LCOE = Depends(),
    filters: Filters = Depends(),
):
    """Return id of export operation and start it"""
    if not lcoe.capacity_factor:
        raise HTTPException(
            status_code=400, detail="Requires capacity factor to be set"
        )
    hash = get_hash(
        operation=operation,
        country_id=country_id,
        **weights.dict(),
        **lcoe.dict(),
        **filters.dict(),
    )
    name = f"{country_id}-{operation}-{hash}"
    # TODO: connect to fargate task
    # boto3.start_task(arguments, hash, name)

    return {"id": name}


@router.get("/export/status/{id}")
def get_export_status(id: str, response: Response):
    """Return export status"""
    try:
        s3_head(bucket=BUCKET, key=f"export/{id}.tif")
        return dict(status="complete")
    except Exception as e:
        print(e)
        response.status_code = status.HTTP_202_ACCEPTED
        return dict(status="processing")


@router.get("/export/{id}", response_class=FileResponse)
def get_export(id: str):
    """download exported file"""
    response = s3_get(bucket=BUCKET, key=f"export/{id}.tif", full_response=True)

    headers = {
        "cache-control": "private, immutable, max-age=43200",
        "last-modified": format_datetime(response["LastModified"]),
        "content-length": str(response["ContentLength"]),
        "etag": response["ETag"],
    }

    return StreamingResponse(
        response["Body"], media_type=response["ContentType"], headers=headers
    )
