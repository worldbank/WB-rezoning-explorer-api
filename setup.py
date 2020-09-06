"""Setup for rezoning-api."""

from setuptools import find_packages, setup

# Runtime requirements.
inst_reqs = [
    "fastapi",
    "rio-tiler==2.0a11",
    "pydantic",
    "jinja2",
    "geojson_pydantic",
    "shapely",
    "pyproj",
]

extra_reqs = {
    "dev": ["pytest", "pytest-benchmark", "pytest-asyncio"],
    "server": ["uvicorn"],
    "deploy": [
        "docker",
        "attrs~=19.3.0",
        "aws-cdk.core",
        "aws-cdk.aws_lambda",
        "aws-cdk.aws_apigatewayv2",
        "aws-cdk.aws_ecs",
        "aws-cdk.aws_ec2",
        "aws-cdk.aws_autoscaling",
        "aws-cdk.aws_ecs_patterns",
        "aws-cdk.aws_iam",
        "aws-cdk.aws_elasticache",
    ],
    "test": ["moto", "mock", "pytest", "pytest-cov", "pytest-asyncio", "requests"],
}

setup(
    name="rezoning-api",
    version="0.1.0",
    python_requires=">=3",
    description=u"""API for the REZoning project""",
    packages=find_packages(exclude=["tests"]),
    package_data={"rezoning_api": ["templates/*.html"]},
    zip_safe=False,
    install_requires=inst_reqs,
    extras_require=extra_reqs,
)
