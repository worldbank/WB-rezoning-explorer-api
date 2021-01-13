"""Filter endpoints."""
from enum import Enum
import json
import boto3

from fastapi import APIRouter, status, HTTPException
from fastapi.responses import Response

from rezoning_api.utils import s3_head, get_hash
from rezoning_api.core.config import EXPORT_BUCKET, QUEUE_URL
from rezoning_api.models.zone import ExportRequest

router = APIRouter()

s3 = boto3.client("s3")


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
    query: ExportRequest,
    operation: Operation,
    country_id: str,
):
    """Return id of export operation and start it"""
    if not query.lcoe.capacity_factor:
        raise HTTPException(
            status_code=400, detail="Requires capacity factor to be set"
        )

    weights = query.weights
    lcoe = query.lcoe
    filters = query.filters

    hash = get_hash(
        operation=operation,
        country_id=country_id,
        **weights.dict(),
        **lcoe.dict(),
        **filters.dict(),
    )
    name = f"{country_id}-{operation}-{hash}"

    # run export queue processing
    client = boto3.client("sqs")
    client.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(
            dict(
                file_name=f"{name}.tif",
                country_id=country_id,
                operation=operation,
                weights=weights.json(),
                lcoe=lcoe.json(),
                filters=filters.json(),
            )
        ),
    )

    return {"id": name}


@router.get("/export/status/{id}")
def get_export_status(id: str, response: Response):
    """Return export status"""
    try:
        key = f"export/{id}.tif"
        s3_head(bucket=EXPORT_BUCKET, key=key)
        url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": EXPORT_BUCKET, "Key": key}, ExpiresIn=300
        )
        return dict(status="complete", url=url)
    except Exception as e:
        print(e)
        response.status_code = status.HTTP_202_ACCEPTED
        return dict(status="processing")
