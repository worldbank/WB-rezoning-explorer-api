## How to run the backend locally

The API of rezoning contains 2 parts: the rezoning api and the export function. Each need to be ran individually. But before running any of the 2, localstack needs to be running.

## Running localstack:
- Make sure you have localstack setup by following instructions from [LocalStack CLI offical install instruction](https://docs.localstack.cloud/getting-started/installation/#localstack-cli)
- Start LocalStack in the background: 
```sh
localstack start -d
aws sqs create-queue --queue-name export-queue --endpoint-url=http://localhost:4566/
```
- Create the export bucket needed to store export calculation results:
```sh
aws s3 mb s3://rezoning-exports --endpoint-url=http://localhost:4566/
```
- Create the export queue used to communicate the exporting requests between the API and the export function:
```sh
aws s3 mb s3://rezoning-exports --endpoint-url=http://localhost:4566/
```

## Running Rezoning API:
In order to work with Rezoning locally, you need AWS access to the processed data (Currently around 330Gb of data) and a certain Airtable. 

You can do this by setting the follwing envirnment variables:
```sh
export AIRTABLE_KEY=<%AIRTABLE_KEY> AWS_ACCESS_KEY_ID=<%AWS_ACCESS_KEY_ID> AWS_SECRET_ACCESS_KEY=<%AWS_SECRET_ACCESS_KEY>
```

If your network is slow, you need to download data using the following command:

```sh
aws s3 cp s3://gre-processed-data/ ~/rezoning-data/
```

The command will make sure every file in the AWS data bucket will be copied over locally to the rezoning-data directory in your home directory.

To work with the local data, the following envirnment variables need to be set:
```sh
export REZONING_IS_LOCAL_DEV=True
export REZONING_LOCAL_DATA_PATH=<%YOUR_DATA_PATH>
```

Install the dependencies using:

```sh
pip install -e '.[dev]'
```

Start the server using:

```sh
python -m uvicorn rezoning_api.main:app --reload
```

### Run export function locally:
```sh
export AIRTABLE_KEY=<%AIRTABLE_KEY> AWS_ACCESS_KEY_ID=<%AWS_ACCESS_KEY_ID> AWS_SECRET_ACCESS_KEY=<%AWS_SECRET_ACCESS_KEY>
REGION=us-east-2 QUEUE_NAME=export-queue python ./export/export.py
```
