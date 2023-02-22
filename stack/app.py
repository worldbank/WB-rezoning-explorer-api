"""Construct App."""

from typing import Any

import os

from aws_cdk import (
    core,
    aws_s3 as s3,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_lambda,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as apigw_int,
    aws_ecr as ecr,
    # aws_elasticache as escache,
)
import docker
import config


DEFAULT_ENV = dict(
    CPL_TMPDIR="/tmp",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    GDAL_CACHEMAX="75%",
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    GDAL_HTTP_MULTIPLEX="YES",
    GDAL_HTTP_VERSION="2",
    PYTHONWARNINGS="ignore",
    VSI_CACHE="TRUE",
    VSI_CACHE_SIZE="1000000",
)


class rezoningApiLambdaStack(core.Stack):
    """
    rezoning API Lambda Stack
    This code is freely adapted from
    - https://github.com/leothomas/titiler/blob/10df64fbbdd342a0762444eceebaac18d8867365/stack/app.py author: @leothomas
    - https://github.com/ciaranevans/titiler/blob/3a4e04cec2bd9b90e6f80decc49dc3229b6ef569/stack/app.py author: @ciaranevans
    """

    def __init__(
        self,
        scope: core.Construct,
        id: str,
        memory: int = 1024,
        timeout: int = 30,
        concurrent: int = 100,
        code_dir: str = "./",
        **kwargs: Any,
    ) -> None:
        """Define stack."""
        super().__init__(scope, id, **kwargs)

        # hardcoded VPC
        vpc = ec2.Vpc.from_lookup(self, f"{id}-vpc", vpc_id="vpc-dfff4bb4")

        # hardcode bucket (shared across env)
        bucket = s3.Bucket.from_bucket_name(
            self, f"{id}-export-bucket", "rezoning-exports"
        )

        s3_access_policy = iam.PolicyStatement(
            actions=["s3:*"],
            resources=[
                bucket.bucket_arn,
                f"{bucket.bucket_arn}/*",
                f"arn:aws:s3:::{config.BUCKET}",
                f"arn:aws:s3:::{config.BUCKET}/*",
            ],
        )

        cluster = ecs.Cluster(
            self,
            f"{id}-ExportProcessingCluster",
            vpc=vpc,
            cluster_name=f"{config.CLUSTER_NAME}-{config.STAGE}",
        )

        cluster.add_capacity(
            id=f"{id}-autoscaling-capacity",
            instance_type=ec2.InstanceType("t2.large"),
            desired_capacity=1,
        )

        image = ecs.ContainerImage.from_ecr_repository(
            ecr.Repository.from_repository_name(
                self, f"{id}-export-repo", repository_name="export-queue-processing"
            )
        )

        processor_env = DEFAULT_ENV.copy()
        processor_env.update(
            dict(
                REGION="us-east-2",
                GDAL_TIFF_INTERNAL_MASK="YES",
            )
        )

        queue_processor = ecs_patterns.QueueProcessingEc2Service(
            self,
            f"{id}-queue-processor",
            cpu=1800,
            memory_limit_mib=7600,
            image=image,
            cluster=cluster,
            environment=processor_env,
        )

        queue_processor.task_definition.task_role.add_to_policy(s3_access_policy)

        sqs_access_policy = iam.PolicyStatement(
            actions=["sqs:*"],
            resources=[queue_processor.sqs_queue.queue_arn],
        )

        # add cache
        # vpc = ec2.Vpc(self, f"{id}-vpc")
        # sb_group = escache.CfnSubnetGroup(
        #     self,
        #     f"{id}-subnet-group",
        #     description=f"{id} subnet group",
        #     subnet_ids=[sb.subnet_id for sb in vpc.private_subnets],
        # )

        # sg = ec2.SecurityGroup(self, f"{id}-cache-sg", vpc=vpc)
        # cache = escache.CfnCacheCluster(
        #     self,
        #     f"{id}-cache",
        #     cache_node_type=config.CACHE_NODE_TYPE,
        #     engine=config.CACHE_ENGINE,
        #     num_cache_nodes=config.CACHE_NODE_NUM,
        #     vpc_security_group_ids=[sg.security_group_id],
        #     cache_subnet_group_name=sb_group.ref,
        # )

        # vpc_access_policy_statement = iam.PolicyStatement(
        #     actions=[
        #         "logs:CreateLogGroup",
        #         "logs:CreateLogStream",
        #         "logs:PutLogEvents",
        #         "ec2:CreateNetworkInterface",
        #         "ec2:DescribeNetworkInterfaces",
        #         "ec2:DeleteNetworkInterface",
        #     ],
        #     resources=["*"],
        # )

        lambda_env = DEFAULT_ENV.copy()
        lambda_env.update(
            dict(
                MODULE_NAME="rezoning_api.main",
                VARIABLE_NAME="app",
                WORKERS_PER_CORE="1",
                LOG_LEVEL="error",
                QUEUE_URL=queue_processor.sqs_queue.queue_url,
                AIRTABLE_KEY=os.environ["AIRTABLE_KEY"],
                # MEMCACHE_HOST=cache.attr_configuration_endpoint_address,
                # MEMCACHE_PORT=cache.attr_configuration_endpoint_port,
            )
        )

        lambda_function = aws_lambda.Function(
            self,
            f"{id}-lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_7,
            code=self.create_package(code_dir),
            handler="handler.handler",
            memory_size=memory,
            reserved_concurrent_executions=concurrent,
            timeout=core.Duration.seconds(timeout),
            environment=lambda_env,
            # vpc=vpc,
        )
        lambda_function.add_to_role_policy(s3_access_policy)
        lambda_function.add_to_role_policy(sqs_access_policy)

        # defines an API Gateway Http API resource backed by our lambda function.
        apigw.HttpApi(
            self,
            f"{id}-endpoint",
            default_integration=apigw_int.HttpLambdaIntegration(
                handler=lambda_function
            ),
        )

    def create_package(self, code_dir: str) -> aws_lambda.Code:
        """Build docker image and create package."""
        print("building lambda package via docker")
        print(f"code dir: {code_dir}")
        client = docker.from_env()
        print("docker client up")
        response = client.api.build( path=code_dir, dockerfile="Dockerfiles/lambda/Dockerfile", tag="lambda:latest" )
        print( "====================================" )
        print( *response, sep='\n' )
        print( "====================================" )
        # client.images.build(
        #     path=code_dir,
        #     dockerfile="Dockerfiles/lambda/Dockerfile",
        #     tag="lambda:latest",
        # )
        print("docker image built")
        client.containers.run(
            image="lambda:latest",
            command="/bin/sh -c 'cp /tmp/package.zip /local/package.zip'",
            remove=True,
            volumes={os.path.abspath(code_dir): {"bind": "/local/", "mode": "rw"}},
            user=0,
        )

        return aws_lambda.Code.asset(os.path.join(code_dir, "package.zip"))


app = core.App()

# Tag infrastructure
for key, value in {
    "Project": config.PROJECT_NAME,
    "Stack": config.STAGE,
    "Owner": os.environ.get("OWNER"),
    "Client": os.environ.get("CLIENT"),
}.items():
    if value:
        core.Tag.add(app, key, value)

lambda_stackname = f"{config.PROJECT_NAME}-lambda-{config.STAGE}"
rezoningApiLambdaStack(
    app,
    lambda_stackname,
    memory=config.MEMORY,
    timeout=config.TIMEOUT,
    concurrent=config.MAX_CONCURRENT,
    env=dict(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    ),
)

app.synth()
