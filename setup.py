"""Setup for rezoning-api."""

from setuptools import find_packages, setup

# Runtime requirements.
inst_reqs = [
    "fastapi==0.65.3",
    "pydantic==1.10.5",
    "jinja2==3.0.3",
    "geojson_pydantic==0.3.4",
    "shapely==2.0.1",
    "xarray==0.21.1",
    "aiofiles==0.7.0",
    "rio-tiler==3.1.6",
    "mercantile==1.2.1",
    "rasterio==1.3.4",
    "requests",
]

extra_reqs = {
    "dev": ["pytest", "pytest-benchmark", "pytest-asyncio"],
    "server": ["uvicorn"],
    "deploy": [
        "docker",
        "attrs",
        "aws-cdk.core==1.181.1",
        "aws-cdk.aws_lambda==1.181.1",
        "aws-cdk.aws_apigatewayv2==1.181.1",
        "aws-cdk.aws_apigatewayv2_integrations==1.181.1",
        "aws-cdk.aws_ecs==1.181.1",
        "aws-cdk.aws_ec2==1.181.1",
        "aws-cdk.aws_autoscaling==1.181.1",
        "aws-cdk.aws_ecs_patterns==1.181.1",
        "aws-cdk.aws_iam==1.181.1",
        "aws-cdk.aws_elasticache==1.181.1",
        "aws-cdk.aws_logs==1.181.1",
        "aws-cdk.aws_ecr==1.181.1",
        "aws-cdk.aws_s3==1.181.1",
    ],
    "test": ["moto", "mock", "pytest", "pytest-cov", "pytest-asyncio", "requests"],
}

setup(
    name="rezoning-api",
    version="1.2.0",
    python_requires=">=3",
    description=u"""API for the REZoning project""",
    packages=find_packages(exclude=["tests"]),
    package_data={
        "rezoning_api": [
            "templates/*.html",
            "db/countries.geojson",
            "db/eez.geojson",
            "db/layers.json",
            "db/cf.json",
            "db/irena.json",
            "db/regions.json",
            "db/regions/*.geojson",
            "db/regions_eez/*.geojson",
            "db/api/minmax/*.json",
        ]
    },
    zip_safe=False,
    install_requires=inst_reqs,
    extras_require=extra_reqs,
)
