FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8-slim

ENV CURL_CA_BUNDLE /etc/ssl/certs/ca-certificates.crt

COPY README.md /app/README.md
COPY rezoning_api/ /app/rezoning_api/
COPY setup.py /app/setup.py
COPY layers.json /app/layers.json

RUN pip install -e /app/. --no-cache-dir