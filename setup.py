"""Setup for rezoning-api."""

from setuptools import find_packages, setup

# Runtime requirements.
inst_reqs = [
    "pytest",
    "pytest-benchmark",
    "pytest-asyncio",
    "rasterio",
]

setup(
    name="rezoning-api",
    version="0.0.1",
    python_requires=">=3",
    description=u"""API for the REZoning project""",
    packages=find_packages(exclude=["tests"]),
    zip_safe=False,
    install_requires=inst_reqs,
)