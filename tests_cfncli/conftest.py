import os

import pytest
from moto import mock_aws

TEST = "TEST"


@pytest.fixture(autouse=True)
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ.pop("AWS_PROFILE", None)
    os.environ["AWS_ACCESS_KEY_ID"] = TEST
    os.environ["AWS_SECRET_ACCESS_KEY"] = TEST
    os.environ["AWS_SECURITY_TOKEN"] = TEST
    os.environ["AWS_SESSION_TOKEN"] = TEST


@pytest.fixture
def aws(aws_credentials):
    """Mocked AWS services."""
    with mock_aws():
        yield
