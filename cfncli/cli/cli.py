import boto3
import click
from botocore.exceptions import ProfileNotFound
import click_log
import logging

from cfncli.helpers import (
    get_account_id,
    parse_prefix_list,
    raise_for_click
)

from .cleanup_environment import cleanup_env


logger = logging.getLogger("CfnCliLogger")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    "-p",
    "--profile",
    required=False,
    help="AWS profile",
    envvar="AWS_PROFILE",
)
@click.option(
    "-r", "--region", required=False, help="AWS region", envvar="AWS_REGION"
)
@click.option(
    "-ac",
    "--account-id",
    required=False,
    help="AWS Account Id",
    envvar="AWS_ACCOUNT_ID",
)

@click.pass_context
def cli(ctx, profile, region, account_id):
    ctx.ensure_object(dict)
    try:
        boto3.setup_default_session(profile_name=profile, region_name=region)
    except ProfileNotFound as error:
        raise click.UsageError(str(error))
    region = region or boto3.DEFAULT_SESSION.region_name
    if not region:
        raise click.UsageError("Specify --region or configure a default AWS Region")
    caller_account_id = get_account_id(region)
    if account_id and account_id != caller_account_id:
        raise click.UsageError(
            f"--account-id {account_id} does not match the account of the credentials ({caller_account_id})"
        )
    account_id = caller_account_id

    COMMON_CONTEXT = {
        "PROFILE": profile,
        "REGION": region,
        "ACCOUNT_ID": account_id,
    }
    ctx.obj.update(COMMON_CONTEXT)

# Nested group for `cfncli dev` commands
@cli.group("dev")
@click.pass_context
def dev(ctx):
    ctx.ensure_object(dict)

@dev.command(
    "cleanup-env", help="Destroy all resources in an environment, USE WITH CAUTION"
)
@click.option(
    "--prefix-list",
    "-pl",
    required=True,
    callback=parse_prefix_list,
    help="Comma-separated list of environment prefixes, USE WITH TRIPLE EXTREME CAUTION",
)
@click.option(
    "-noconfirm",
    "--no-confirm",
    is_flag=True,
    help="Do not prompt for confirmation, USE WITH EXTREME CAUTION",
)
@click.pass_context
@click_log.simple_verbosity_option(logger.name)
def cleanup_env_cli(ctx, no_confirm, prefix_list):
    try:
        cleanup_env(ctx, logger, no_confirm, prefix_list)
    except Exception as e:
        raise_for_click(e)

if __name__ == "__main__":
    cli()
