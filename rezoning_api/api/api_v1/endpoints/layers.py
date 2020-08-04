"""Layer endpoints."""

import json

import boto3
from fastapi import APIRouter, Request

from rezoning_api.core.config import BUCKET

router = APIRouter()

s3 = boto3.client("s3")

def s3_get(bucket: str, key: str):
    """Get AWS S3 Object."""
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()

@router.get(
    "/layers/{group}/"
)
def get_layers(group: str):
    """Return layers list for a given group"""
    layers = s3_get(BUCKET, f'multiband/{group}.json')
    return json.loads(layers).get("layers")
