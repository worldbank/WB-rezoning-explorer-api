"""Config."""
import os

API_VERSION_STR = "/v1"

PROJECT_NAME = "rezoning_api"
BUCKET = "gre-processed-data"
CLUSTER_NAME = "export-cluster"
TASK_NAME = "export"

SERVER_NAME = os.getenv("SERVER_NAME")
SERVER_HOST = os.getenv("SERVER_HOST")
BACKEND_CORS_ORIGINS = os.getenv(
    "BACKEND_CORS_ORIGINS", default="*"
)  # a string of origins separated by commas, e.g: "http://localhost, http://localhost:4200, http://localhost:3000, http://localhost:8080, http://local.dockertoolbox.tiangolo.com"
