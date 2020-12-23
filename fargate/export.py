"""CLI for fargate image for LCOE/Score export"""
import argparse
import json
import boto3

from rezoning_api.db.calc import single_country_lcoe, single_country_score
from rezoning_api.models.zone import Filters, Weights, LCOE
from rezoning_api.core.config import EXPORT_BUCKET


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export LCOE or Score GeoTIFF")
    parser.add_argument("--operation", type=str, help="lcoe or score")
    parser.add_argument("--country_id", type=str)
    parser.add_argument("--file_name", type=str, help="output file name")

    parser.add_argument(
        "--weights", type=str, help="serialized weights object", default="{}"
    )
    parser.add_argument(
        "--filters", type=str, help="serialized filters object", default="{}"
    )
    parser.add_argument("--lcoe", type=str, help="serialized lcoe object", default="{}")

    args = parser.parse_args()

    weights = Weights(**json.loads(args.weights))
    filters = Filters(**json.loads(args.filters))
    lcoe = LCOE(**json.loads(args.lcoe))

    if not args.file_name:
        raise Exception("No file name set")
    file_path = f"export/{args.file_name}"

    operations = ["lcoe", "score"]
    if args.operation not in operations:
        raise Exception(f"operation must be one of: {' '.join(operations)}")

    if args.operation == "lcoe":
        single_country_lcoe(file_path, args.country_id, lcoe, filters)
    else:
        single_country_score(
            file_path,
            args.country_id,
            lcoe,
            filters,
            weights,
        )

    s3 = boto3.client("s3")

    s3.upload_file(file_path, EXPORT_BUCKET, file_path)
