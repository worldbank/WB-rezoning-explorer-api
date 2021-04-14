"""AWS Lambda handler."""

from mangum import Mangum
from rezoning_api.main import app

handler = Mangum(app, lifespan="off")
