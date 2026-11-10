import json

import boto3
import click
import pytest
from botocore.exceptions import ProfileNotFound
from click.testing import CliRunner

from cfncli.cli import cleanup_environment as ce
from cfncli.cli.cli import cli
from cfncli.helpers import parse_prefix_list

REGION = "us-east-1"


def test_matches_prefix():
    assert ce.matches_prefix("sampleforcleanup-Stack", ["sampleforcleanup"])
    assert ce.matches_prefix("/aws/lambda/sampleforcleanup-fn", ["sampleforcleanup"])
    assert not ce.matches_prefix("prod-sampleforcleanup", ["sampleforcleanup"])


@pytest.mark.parametrize("value", [",", "dev,", " ", "dev, ,qa"])
def test_parse_prefix_list_rejects_empty(value):
    with pytest.raises(click.BadParameter):
        parse_prefix_list(None, None, value)


def test_parse_prefix_list():
    assert parse_prefix_list(None, None, "dev, qa") == ["dev", "qa"]


def test_cli_requires_prefix_list(aws):
    result = CliRunner().invoke(cli, ["-r", REGION, "dev", "cleanup-env"])
    assert result.exit_code == 2
    assert "Missing option '--prefix-list'" in result.output


def test_cli_rejects_wrong_account_id(aws):
    result = CliRunner().invoke(cli, ["-r", REGION, "-ac", "999999999999", "dev", "cleanup-env", "-pl", "dev"])
    assert result.exit_code == 2
    assert "does not match the account of the credentials" in result.output


def test_cli_uses_profile(aws):
    result = CliRunner().invoke(cli, ["-p", "cfncli-missing-profile", "-r", REGION, "dev", "cleanup-env", "-pl", "dev"])
    assert isinstance(result.exception, ProfileNotFound)


def test_cli_prompt_defaults_to_no(aws):
    result = CliRunner().invoke(cli, ["-r", REGION, "dev", "cleanup-env", "-pl", "dev"], input="\n")
    assert "[y/N]" in result.output
    assert "No S3 buckets" not in result.output  # nothing gathered after the default answer


def test_gather_s3_buckets_is_prefix_and_region_scoped(aws):
    boto3.client("s3", region_name=REGION).create_bucket(Bucket="dev-us-bucket")
    boto3.client("s3", region_name=REGION).create_bucket(Bucket="prod-dev-data")
    boto3.client("s3", region_name="eu-west-1").create_bucket(
        Bucket="dev-eu-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
    )
    assert ce.gather_s3_buckets(["dev"], REGION) == ["dev-us-bucket"]


def test_preprocessing_targets_only_stack_resources(aws):
    ddb = boto3.client("dynamodb", region_name=REGION)
    ddb.create_table(
        TableName="dev-unmanaged-table",
        AttributeDefinitions=[{"AttributeName": "k", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "k", "KeyType": "HASH"}],
        BillingMode="PAY_PER_REQUEST",
    )
    template = {
        "Resources": {
            "Table": {
                "Type": "AWS::DynamoDB::Table",
                "Properties": {
                    "TableName": "dev-stack-table",
                    "AttributeDefinitions": [{"AttributeName": "k", "AttributeType": "S"}],
                    "KeySchema": [{"AttributeName": "k", "KeyType": "HASH"}],
                    "BillingMode": "PAY_PER_REQUEST",
                },
            }
        }
    }
    boto3.client("cloudformation", region_name=REGION).create_stack(
        StackName="dev-stack", TemplateBody=json.dumps(template)
    )
    resources = ce.gather_resources(["dev"], REGION)
    assert resources["cloudformation_stacks"] == ["dev-stack"]
    assert resources["ddb_tables"] == ["dev-stack-table"]


def test_empty_ecr_repository_with_more_than_100_images(mocker):
    client = mocker.Mock()
    client.get_paginator.return_value.paginate.return_value = [
        {"imageIds": [{"imageDigest": f"sha256:{i:064x}", "imageTag": f"t{i}"} for i in range(100)]},
        {"imageIds": [{"imageDigest": f"sha256:{i:064x}", "imageTag": f"t{i}"} for i in range(100, 150)]},
    ]
    mocker.patch("cfncli.cli.cleanup_environment.boto3.client", return_value=client)
    ce.empty_ecr_repositories(["dev-repo"], REGION)
    batches = [call.kwargs["imageIds"] for call in client.batch_delete_image.call_args_list]
    assert [len(batch) for batch in batches] == [100, 50]
    assert len({image["imageDigest"] for batch in batches for image in batch}) == 150
