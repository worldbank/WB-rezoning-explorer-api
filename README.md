# rezoning-api

Reneweable Energy Zone Calculations. Backend to https://github.com/developmentseed/rezoning-web

Deployed at https://cb1d9tl7ve.execute-api.us-east-2.amazonaws.com/

Documentation at https://cb1d9tl7ve.execute-api.us-east-2.amazonaws.com/docs

## Primary functions

This API exposes two primary functions:
1. A tile server to display areas which satisfy a set of geospatial filters (e.g. areas within 5000 meters of a road and 10000 meters away from transmission lines)
2. The ability to calculate "zone statistics" for a given area of interest, including Levelized Cost of Energy (LCOE) and "zone score" based on user provided weights

### Tile Server

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

Each parameter is described in more detail at https://cb1d9tl7ve.execute-api.us-east-2.amazonaws.com/docs

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

The latter command requires two environment variables `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` to be set in order to access the spatial data stored on AWS S3.

### Deploy

The application is built to deploy on AWS via [AWS CDK](https://aws.amazon.com/cdk/). The resulting stack consists of an API Gateway and a Lambda function. It can be deployed from the commandline with 

```sh
cdk deploy
```

but is generally done via a [CI/CD pipeline](.github/workflows/ci.yml) running with Github Actions.
