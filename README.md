# rezoning-api

Reneweable Energy Zone Calculations. Backend to https://github.com/developmentseed/rezoning-web

Deployed at https://d2b8erzy6y494p.cloudfront.net/

Documentation at https://d2b8erzy6y494p.cloudfront.net/docs

## Primary functions

This API exposes four primary functions:
1. A tile server to display areas which satisfy a set of geospatial filters (e.g. areas within 5000 meters of a road and 10000 meters away from transmission lines)
2. The ability to calculate "zone statistics" for a given area of interest, including Levelized Cost of Energy (LCOE) and "zone score" based on user provided weights
3. A tile server to display LCOE calculations at a pixel level
4. A tile server to display contextual data (stored as Cloud-Optimized GeoTIFFs)

It also provides a variety of other metadata endpoints to define the schema and layers needed for these functions.

### Filter Tile Server

![demonstration of the tile server of Africa](images/rezoning-api-filter.gif)

The tile server is available as an XYZ endpoint at: `/v1/filter/{z}/{x}/{y}.png`. It further accepts two path parameters:

`filter=0,1000|500,1000|...`: a pipe separated list of distance ranges in meters (e.g. `0,5000`) from a given feature. The list of features which have distance layers is available at `/v1/filter/layers`

`color=45,39,88,178`: a comma separated list of RGBA values to display the filtered areas as. All values, including opacity, are 0-255.

A UI demonstration of this functionality is available at `/v1/demo`. All data is made available at 500m resolution.

### Zone Statistics

This function is relatively complicated but has sensible defaults. A rough summary of the process:
1. User submits an area of interest (AOI) as a [GeoJSON](https://geojson.org/) `Polygon` and a set of filters matching the above format, along with optional parameters to override defaults.
2. The API calculates LCOE for each pixel in the AOI and matching the spatial filters
3. The API calculates a zone score by combining user provided weights, the LCOE components, and other underlying data like population density and slope
4. The API returns these values in aggreate and a mean value per pixel

`/v1/zone`: accepts a POST request with the following form:

```json
{
    "aoi": {},
    "weights": {},
    "lcoe": {} 
}
```

and returns:

```json
{
    "lcoe": 5,
    "lcoe_density": 1,
    "zone_score": 0.7
}
```

Each parameter is described in more detail at https://d2b8erzy6y494p.cloudfront.net/docs

## Development

This API is developed with [FastAPI](https://fastapi.tiangolo.com/)

### Run locally

Install dependencies

```sh
pip install -e '.[dev]'
```

Serve 

```sh
uvicorn rezoning_api.main:app --reload
```

The latter command requires three environment variables `AWS_ACCESS_KEY_ID`,  `AWS_SECRET_ACCESS_KEY`, and `AIRTABLE_KEY` to be set in order to access the spatial data stored on AWS S3 and additional defaults stored on Airtable.

### Deploy

The application is built to deploy on AWS via [AWS CDK](https://aws.amazon.com/cdk/). The resulting stack consists of an API Gateway and a Lambda function. It can be deployed from the commandline with 

```sh
cdk deploy
```

but is generally done via a [CI/CD pipeline](.github/workflows/ci.yml) running with Github Actions.

### Additional Notes

- The ECR Repository and docker image for exporting files are not deployed automatically. The Dockerfile is available at `export/Dockerfile` and can be deployed like:
```
docker build . -t export-queue-processing -f export/Dockerfile
docker tag export-queue-processing 497760869739.dkr.ecr.us-east-2.amazonaws.com/export-queue-processing:latest
`aws ecr get-login --region=us-east-2 --no-include-email`
docker push 497760869739.dkr.ecr.us-east-2.amazonaws.com/export-queue-processing
```
- There is an additional vector tile server for certain infrastructure layers hosted by Development Seed. It is available at reztileserver.com
- The production API endpoint is behind a manually configured CloudFront Origin for performance enhancement.