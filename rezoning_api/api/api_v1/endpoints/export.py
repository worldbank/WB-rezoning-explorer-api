"""Filter endpoints."""
from enum import Enum
from email.utils import format_datetime
import boto3

from fastapi import APIRouter, status, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse

from rezoning_api.utils import s3_head, s3_get, get_hash
from rezoning_api.core.config import BUCKET, CLUSTER_NAME, TASK_NAME
from rezoning_api.models.zone import ExportRequest

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
    print(TASK_NAME, CLUSTER_NAME)
    # run fargate task
    client = boto3.client("ecs")
    # TODO: unhardcode container name
    client.run_task(
        cluster=CLUSTER_NAME,
        launchType="FARGATE",
        count=1,
        taskDefinition=TASK_NAME,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [
                    "subnet-06c1403cc7d78526d",
                ],
                "assignPublicIp": "DISABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "container-definition-rezoning-api-lambda-dev",
                    "command": [
                        "python",
                        "export.py",
                        "--file_name",
                        f"{name}.tif",
                        "--country_id",
                        country_id,
                        "--operation",
                        operation,
                        "--weights",
                        weights.json(),
                        "--lcoe",
                        lcoe.json(),
                        "--filters",
                        filters.json(),
                    ],
                }
            ]
        },
    )

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
