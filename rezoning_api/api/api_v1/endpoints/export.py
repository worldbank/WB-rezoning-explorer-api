"""Filter endpoints."""
from enum import Enum
import json
import boto3
from botocore.client import Config

from fastapi import APIRouter, status, HTTPException
from fastapi.responses import Response

from rezoning_api.utils import get_hash
from rezoning_api.core.config import EXPORT_BUCKET, QUEUE_URL, IS_LOCAL_DEV, LOCALSTACK_ENDPOINT_URL
from rezoning_api.models.zone import ExportRequest

router = APIRouter()

s3 = boto3.client("s3", config=Config(signature_version="s3v4"))


class Operation(str, Enum):
    """possible export operations"""

    LCOE = "lcoe"
    SCORE = "score"


@router.post(
    "/export/{operation}/{country_id}/{resource}",
    responses={201: dict(description="start export processing for a given country")},
    name="export",
)
def export(
    query: ExportRequest,
    operation: Operation,
    country_id: str,
    resource: str,
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
        resource=resource,
        **weights.dict(),
        **lcoe.dict(),
        **filters.dict(),
    )
    id = f"{country_id}-{operation}-{resource}-{hash}"
    file_name = f"WBG-REZoning-{id}.tif"

    # run export queue processing
    client = boto3.client("sqs")
    if IS_LOCAL_DEV:
        client = boto3.client("sqs", endpoint_url=LOCALSTACK_ENDPOINT_URL)
        queue_url = client.get_queue_url(QueueName="export-queue")
    client.send_message(
        QueueUrl=queue_url["QueueUrl"] if IS_LOCAL_DEV else QUEUE_URL,
        MessageBody=json.dumps(
            dict(
                file_name=file_name,
                country_id=country_id,
                operation=operation,
                resource=resource,
                weights=weights.json(),
                lcoe=lcoe.json(),
                filters=filters.json(),
            )
        ),
    )

    return {"id": id}


@router.get("/export/status/{id}")
def get_export_status(id: str, response: Response):
    """Return export status"""
    if IS_LOCAL_DEV:
        s3 = boto3.client("s3", endpoint_url=LOCALSTACK_ENDPOINT_URL)
    try:
        key = f"export/WBG-REZoning-{id}.tif"
        s3.head_object(Bucket=EXPORT_BUCKET, Key=key)
        url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": EXPORT_BUCKET, "Key": key}, ExpiresIn=300
        )
        return dict(status="complete", url=url)
    except Exception as e:
        print(e)
        response.status_code = status.HTTP_202_ACCEPTED
        return dict(status="processing")
