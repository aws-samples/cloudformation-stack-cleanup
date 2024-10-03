import click
import click_log
import logging

from cfncli.helpers import (
    get_account_id,
    get_region,
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
    if not region:
        region = get_region()
    if not account_id:
        account_id = get_account_id(region)

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
    default=None,
    callback=lambda ctx, param, value: value.split(",") if value else None,
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
