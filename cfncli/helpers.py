import json
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import click
import jsonschema

from botocore.exceptions import ClientError
from click import Option, UsageError

from .exceptions import ApplicationException


class MutuallyExclusiveOption(Option):
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop("mutually_exclusive", []))
        help = kwargs.get("help", "")
        if self.mutually_exclusive:
            ex_str = ", ".join(self.mutually_exclusive)
            kwargs["help"] = help + (
                " NOTE: This argument is mutually exclusive with "
                " arguments: [" + ex_str + "]."
            )
        super(MutuallyExclusiveOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise UsageError(
                "Illegal usage: `{}` is mutually exclusive with "
                "arguments `{}`.".format(self.name, ", ".join(self.mutually_exclusive))
            )

        return super(MutuallyExclusiveOption, self).handle_parse_result(ctx, opts, args)



def validate_request(request: dict, schema: dict, logger=None) -> bool:
    try:
        jsonschema.validate(instance=request, schema=schema)
    except jsonschema.ValidationError as validation_error:
        raise validation_error
    return True

def str_to_json(str_input):
    if isinstance(str_input, str):
        try:
            return json.loads(str_input)
        except json.JSONDecodeError:
            pass
    return str_input


def convert_json_fields(item, fields):
    for field in fields:
        if field in item:
            item[field] = str_to_json(item[field])
    return item


def decimal_serializer(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError("Type not serializable")


def generate_response(data, status_code=200):
    return {
        "statusCode": status_code,
        "body": json.dumps(data, default=decimal_serializer),
    }


def get_ssm_parameter(parameter_name: str) -> str:
    """
    Retrieve the value of an SSM parameter.

    :param parameter_name: Name of the SSM parameter.
    :return: Value of the SSM parameter.
    :raises ApplicationException: If the parameter is not found or any other AWS-related error occurs.
    """
    ssm_client = boto3.client("ssm")
    try:
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as e:
        # You can further distinguish different types of ClientErrors by checking e.response['Error']['Code']
        if e.response["Error"]["Code"] == "ParameterNotFound":
            raise ApplicationException(f"Parameter {parameter_name} not found.")
        raise ApplicationException(
            f"An error occurred while fetching the SSM parameter: {str(e)}"
        )


def get_region():
    session = boto3.session.Session()
    return session.region_name


def get_account_id(region: str):
    """
    Returns the AWS account ID.
    """
    print(f"https://sts.{region}.amazonaws.com")
    sts_client = boto3.client(
        "sts",
        endpoint_url=f"https://sts.{region}.amazonaws.com",
        region_name=region
    )
    return sts_client.get_caller_identity()["Account"]




def sanitize_json(value):
    if isinstance(value, dict):
        return {k: sanitize_json(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [sanitize_json(item) for item in value]
    elif isinstance(value, str):
        # Attempt to parse the string only if it contains '{' or '['
        if "{" in value or "[" in value:
            try:
                parsed_json = json.loads(value)
                return sanitize_json(parsed_json)
            except json.JSONDecodeError:
                pass
        return value  # Return the original string if not a JSON object/array or if parsing fails
    elif isinstance(value, Decimal):
        # Convert Decimal to string and attempt to parse as JSON
        try:
            parsed_json = json.loads(str(value))
            return sanitize_json(parsed_json)
        except json.JSONDecodeError:
            return value
    else:
        return value


def pretty_json(value_dict):
    return json.dumps(
        sanitize_json(value_dict), indent=4, sort_keys=True, ensure_ascii=False
    )



def generate_utc_timestamp() -> str:
    """
    Generates a timestamp in ISO 8601 format with UTC timezone ('Z' suffix).

    Returns:
        str: A timestamp string in the format 'YYYY-MM-DDTHH:MM:SS.ssssssZ'.
    """
    # Generate the current UTC time with fractional seconds.
    return datetime.now(timezone.utc).isoformat() + "Z"


def raise_for_click(message: str) -> None:
    """
    Raises an exception in a style consistent with Click's CLI error handling.

    Args:
        message (str): The error message to be displayed.
    """
    raise click.ClickException(click.style(message, fg="red"))


def get_boto3_session(role_arn):
    session_name = "route53_role_ec2"

    # Create a new session using the IAM role ARN
    sts_client = boto3.client("sts")

    # Assume the IAM role and get temporary credentials
    response = sts_client.assume_role(RoleArn=role_arn, RoleSessionName=session_name)

    # Create a new session with the temporary credentials
    session = boto3.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )
    return session

    # Function to encrypt the plaintext




