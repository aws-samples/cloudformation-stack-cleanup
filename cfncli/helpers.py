import boto3
import click


def get_account_id(region: str):
    """
    Returns the AWS account ID.
    """
    sts_client = boto3.client(
        "sts",
        endpoint_url=f"https://sts.{region}.amazonaws.com",
        region_name=region
    )
    return sts_client.get_caller_identity()["Account"]


def parse_prefix_list(ctx, param, value):
    """Splits a comma-separated prefix list and rejects empty prefixes."""
    prefixes = [prefix.strip() for prefix in value.split(",")]
    if not all(prefixes):
        raise click.BadParameter("prefixes must not be empty")
    return prefixes


def raise_for_click(message: str) -> None:
    """
    Raises an exception in a style consistent with Click's CLI error handling.

    Args:
        message (str): The error message to be displayed.
    """
    raise click.ClickException(click.style(message, fg="red"))
