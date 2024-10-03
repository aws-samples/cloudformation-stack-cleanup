import os

import boto3
import pytest
from moto import mock_dynamodb

TEST = "TEST"


@pytest.fixture(autouse=True)
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = TEST
    os.environ["AWS_SECRET_ACCESS_KEY"] = TEST
    os.environ["AWS_SECURITY_TOKEN"] = TEST
    os.environ["AWS_SESSION_TOKEN"] = TEST


@pytest.fixture
def dynamodb_client(aws_credentials):
    """DynamoDB mock client."""
    with mock_dynamodb():
        conn = boto3.client("dynamodb", region_name="us-west-2")
        yield conn


@pytest.fixture
def dynamodb_resource(aws_credentials):
    """DynamoDB mock resource."""
    with mock_dynamodb():
        conn = boto3.resource("dynamodb", region_name="us-west-2")
        yield conn
