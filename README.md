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

`filter=0,1000|500,1000|...`: a pipe separated list of distance ranges in meters (e.g. `0,5000`) from a given feature. The list of distance layers is available at `/v1/filter/layers`

`color=45,39,88,178`: a comma separated list of RGBA values to display the filtered areas as. All values, including opacity, are 0-255.

A UI demonstration of this functionality is available at `/v1/demo`

### Zone Statistics

This function is relatively complicated but has sensible defaults. A rough summary of the process:
1. User submits an area of interest (AOI) as a [GeoJSON](https://geojson.org/) `Polygon` and a set of filters matching the above format, along with optional parameters to override defaults.
2. 
