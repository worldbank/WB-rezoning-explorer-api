"""CLI for fargate image for LCOE/Score export"""
import json
import logging
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

from rezoning_api.db.calc import single_country_lcoe, single_country_score
from rezoning_api.models.zone import Filters, Weights, LCOE
from rezoning_api.utils import s3_head
from rezoning_api.core.config import EXPORT_BUCKET, IS_LOCAL_DEV, LOCALSTACK_ENDPOINT_URL

logger = logging.getLogger("exporter")
logging.getLogger("botocore.credentials").disabled = True
logging.getLogger("botocore.utils").disabled = True
logging.getLogger("rio-tiler").setLevel(logging.ERROR)


def _parse_message(message):
    if message.get("Records"):
        record = message["Records"][0]
        message = json.loads(record["body"])

    message["weights"] = json.loads(message["weights"])
    message["filters"] = json.loads(message["filters"])
    message["lcoe"] = json.loads(message["lcoe"])
    return message


def process(message):
    """call processing function with the correct arguments"""
    logger.warning(message)
    weights = Weights(**message["weights"])
    filters = Filters(**message["filters"])
    lcoe = LCOE(**message["lcoe"])

    if not message["file_name"]:
        logger.error("No file name set")
        return

    file_path = f"export/{message['file_name']}"

    # if the file has already been processed, stop
    try:
        s3_head(EXPORT_BUCKET, file_path)
        logger.info(f"{file_path} has already been processed, skipping.")
        return
    except ClientError:
        pass

    operations = ["lcoe", "score"]
    if message["operation"] not in operations:
        logger.error(f"operation must be one of: {' '.join(operations)}")
        return

    resources = ["solar", "wind", "offshore"]
    if message["resource"] not in resources:
        logger.error(f"resource must be one of {' '.join(resources)}")

    if message["operation"] == "lcoe":
        single_country_lcoe(
            file_path, message["country_id"], message["resource"], lcoe, filters
        )
    else:
        single_country_score(
            file_path,
            message["country_id"],
            message["resource"],
            lcoe,
            filters,
            weights,
        )

    if IS_LOCAL_DEV:
        s3 = boto3.client("s3", endpoint_url=LOCALSTACK_ENDPOINT_URL)
    else:
        s3 = boto3.client("s3")

    s3.upload_file(file_path, EXPORT_BUCKET, file_path)


def main():
    """Pull Message and Process."""
    region_name = os.environ["REGION"] if "REGION" in os.environ else None
    queue_name = os.environ["QUEUE_NAME"] if "QUEUE_NAME" in os.environ else None

    sqs = None
    if IS_LOCAL_DEV:
        sqs = boto3.resource("sqs", endpoint_url=LOCALSTACK_ENDPOINT_URL)
    else:
        sqs = boto3.resource("sqs", region_name=region_name)

    # Get the queue
    try:
        queue = sqs.get_queue_by_name(QueueName=queue_name)
    except ClientError:
        logger.warning(f"SQS Queue '{queue_name}' ({region_name}) not found")
        sys.exit(1)

    while True:
        message = False
        for message in queue.receive_messages():
            m = _parse_message(json.loads(message.body))
            logger.debug(m)
            t1 = time.time()
            process(m)
            logger.warning(f"processing time: {time.time() - t1} sec.")

            # Let the queue know that the message is processed
            message.delete()

        if not message:
            # logger.warning("No message in Queue, will sleep for 3 seconds...")
            time.sleep(3)  # if no message, let's wait 60secs


if __name__ == "__main__":
    main()
