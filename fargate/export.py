"""CLI for fargate image for LCOE/Score export"""
import argparse
import json

from rezoning_api.db.calc import single_country_lcoe, single_country_score
from rezoning_api.models.zone import Filters, Weights, LCOE


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

    if args.operation == "lcoe":
        single_country_lcoe(f"export/{args.file_name}", args.country_id, lcoe, filters)
    elif args.operation == "score":
        single_country_score(
            f"export/{args.file_name}",
            args.country_id,
            lcoe,
            filters,
            weights,
        )
    else:
        print("no operation specified, exiting")
