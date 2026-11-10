import boto3
import click
from botocore.exceptions import ClientError

from cfncli.helpers import raise_for_click


def matches_prefix(name, prefixes):
    """Returns True if any "/"-separated segment of name starts with one of the prefixes."""
    return any(segment.startswith(tuple(prefixes)) for segment in name.split("/"))


def gather_resources(substrings, region):
    """
    Gathers AWS resources including CloudFormation stacks, S3 buckets, and ECR repositories
    based on specified substrings and region.
    """
    stacks = gather_cloudformation_stacks(substrings, region)
    resources = {
        "cloudformation_stacks": stacks,
        "s3_buckets": gather_s3_buckets(substrings, region),
        "ecr_repositories": gather_ecr_repositories(substrings, region),
        "vpc_lambdas": gather_vpc_lambdas(
            gather_stack_resources(stacks, "AWS::Lambda::Function", region), region
        ),
        "ddb_tables": gather_stack_resources(stacks, "AWS::DynamoDB::Table", region),
    }
    return resources


def gather_stack_resources(stack_names, resource_type, region):
    """
    Gathers the physical IDs of resources of the specified type in the specified
    stacks, including their nested stacks.
    """
    client = boto3.client("cloudformation", region_name=region)
    paginator = client.get_paginator("list_stack_resources")
    physical_ids = []
    for stack_name in stack_names:
        for page in paginator.paginate(StackName=stack_name):
            for resource in page["StackResourceSummaries"]:
                if "PhysicalResourceId" not in resource or resource["ResourceStatus"] == "DELETE_COMPLETE":
                    continue
                if resource["ResourceType"] == "AWS::CloudFormation::Stack":
                    physical_ids.extend(
                        gather_stack_resources([resource["PhysicalResourceId"]], resource_type, region)
                    )
                elif resource["ResourceType"] == resource_type:
                    physical_ids.append(resource["PhysicalResourceId"])
    return physical_ids


def gather_unmanaged_resources(substrings, region):
    """
    Gathers unmanaged AWS resources including S3 buckets, SSM parameters, and CloudWatch Log Groups
    based on specified substrings and region.
    """
    resources = {
        "s3_buckets": gather_s3_buckets(substrings, region),
        "ssm_params": gather_ssm_params(substrings, region),
        "log_groups": gather_log_groups(substrings, region),
    }
    return resources


def gather_cloudformation_stacks(substrings, region):
    """
    Gathers CloudFormation parent stacks that include the specified substrings,
    excluding those in DELETE_COMPLETE status, and sorts them by creation time
    so that the oldest stack will get deleted last.
    """
    client = boto3.client("cloudformation", region_name=region)
    stack_infos = []  # Store tuples of (stack name, creation time)
    paginator = client.get_paginator("list_stacks")

    for page in paginator.paginate():
        for stack in page["StackSummaries"]:
            if (
                "DELETE_COMPLETE" not in stack["StackStatus"]
                and "ParentId" not in stack
            ):
                if matches_prefix(stack["StackName"], substrings):
                    stack_infos.append((stack["StackName"], stack["CreationTime"]))

    # Sort stacks by creation time in descending order so newer stacks are deleted first
    sorted_stack_infos = sorted(stack_infos, key=lambda x: x[1], reverse=True)

    # Extract and return only the stack names from the sorted list
    sorted_stacks = [info[0] for info in sorted_stack_infos]
    return sorted_stacks

def gather_s3_buckets(substrings, region):
    """Gathers S3 buckets that include the specified substrings."""
    client = boto3.client("s3", region_name=region)
    buckets = []
    paginator = client.get_paginator("list_buckets")
    for page in paginator.paginate(BucketRegion=region):
        for bucket in page.get("Buckets", []):
            if matches_prefix(bucket["Name"], substrings):
                buckets.append(bucket["Name"])
    return buckets


def gather_ecr_repositories(substrings, region):
    """Gathers ECR repositories that include the specified substrings."""
    client = boto3.client("ecr", region_name=region)
    repositories = []
    paginator = client.get_paginator("describe_repositories")
    for page in paginator.paginate():
        for repo in page["repositories"]:
            if matches_prefix(repo["repositoryName"], substrings):
                repositories.append(repo["repositoryName"])
    return repositories

def gather_log_groups(substrings, region):
    """
    Gathers CloudWatch Log Groups that include the specified substrings.
    """
    client = boto3.client("logs", region_name=region)
    log_groups = []
    paginator = client.get_paginator("describe_log_groups")

    for page in paginator.paginate():
        for log_group in page["logGroups"]:
            if matches_prefix(log_group["logGroupName"], substrings):
                log_groups.append(log_group["logGroupName"])
    return log_groups

def gather_ssm_params(substrings, region):
    """
    Gathers SSM Parameters that follow the naming convention and include
    the specified substrings.
    """
    client = boto3.client("ssm", region_name=region)
    ssm_params = []
    paginator = client.get_paginator("describe_parameters")

    for page in paginator.paginate():
        for param in page["Parameters"]:
            for sub in substrings:
                # env, prefix = sub.split("-")
                if param["Name"].startswith(f"/{sub}/"):
                    ssm_params.append(param["Name"])
                    break

    return ssm_params


def gather_vpc_lambdas(function_names, region):
    """
    Filters the specified Lambda functions to those attached to a VPC.

    :param function_names: List of Lambda function names from the target stacks.
    :param region: AWS region where the Lambda functions are deployed.
    :return: List of Lambda function names to be updated.
    """
    client = boto3.client("lambda", region_name=region)
    lambda_functions = []
    for function_name in function_names:
        configuration = client.get_function_configuration(FunctionName=function_name)
        if configuration.get("VpcConfig", {}).get("VpcId"):
            lambda_functions.append(function_name)
    return lambda_functions


def empty_s3_buckets(bucket_names, region):
    """Empties specified S3 buckets."""
    s3 = boto3.resource("s3", region_name=region)
    for bucket_name in bucket_names:
        bucket = s3.Bucket(bucket_name)
        bucket.object_versions.delete()
        click.secho(f"Emptied S3 bucket: {bucket_name}", fg="red")


def empty_ecr_repositories(repository_names, region):
    """Empties specified ECR repositories."""
    client = boto3.client("ecr", region_name=region)
    paginator = client.get_paginator("list_images")
    for repo_name in repository_names:
        digests = {
            image["imageDigest"]
            for page in paginator.paginate(repositoryName=repo_name)
            for image in page["imageIds"]
        }
        image_ids = [{"imageDigest": digest} for digest in digests]
        # BatchDeleteImage accepts at most 100 image IDs per call
        for start in range(0, len(image_ids), 100):
            client.batch_delete_image(
                repositoryName=repo_name, imageIds=image_ids[start : start + 100]
            )
        if image_ids:
            click.secho(f"Emptied ECR repository: {repo_name}", fg="red")


def delete_cloudformation_stack(stack_name, region):
    """Deletes a single CloudFormation stack and waits for the deletion to complete using a waiter."""
    client = boto3.client("cloudformation", region_name=region)
    try:
        # Initiate stack deletion
        client.delete_stack(StackName=stack_name)
        click.secho(
            f"Initiated deletion of CloudFormation stack: {stack_name}", fg="yellow"
        )

        # Create a waiter to wait for stack deletion to complete
        waiter = client.get_waiter("stack_delete_complete")

        # Wait for the stack to be deleted
        click.secho(f"Waiting for stack {stack_name} to be deleted...", fg="yellow")
        waiter.wait(StackName=stack_name)
        click.secho(
            f"CloudFormation stack {stack_name} deleted successfully.", fg="green"
        )

    except ClientError as e:
        # Specific error handling for stack does not exist scenario
        if (
            e.response["Error"]["Code"] == "ValidationError"
            and "does not exist" in e.response["Error"]["Message"]
        ):
            click.secho(
                f"CloudFormation stack {stack_name} does not exist or is already deleted.",
                fg="yellow",
            )
        else:
            # For other ClientErrors, propagate the error message
            raise_for_click(f"Failed to delete CloudFormation stack {stack_name}: {e}")


def delete_s3_bucket(bucket_name, region):
    """Deletes a single S3 bucket after emptying it."""
    s3 = boto3.resource("s3", region_name=region)
    bucket = s3.Bucket(bucket_name)
    try:
        bucket.object_versions.delete()
        bucket.delete()
        click.secho(f"Deleted S3 bucket: {bucket_name}", fg="red")
    except Exception as e:
        raise_for_click(f"Failed to delete S3 bucket {bucket_name}: {e}")


def delete_ecr_repository(repo_name, region):
    """Deletes a single ECR repository."""
    client = boto3.client("ecr", region_name=region)
    try:
        client.delete_repository(repositoryName=repo_name, force=True)
        click.secho(f"Deleted ECR repository: {repo_name}", fg="red")
    except Exception as e:
        raise_for_click(f"Failed to delete ECR repository {repo_name}: {e}")


def delete_ssm_param(param_name, region):
    """Deletes a single SSM Parameter."""
    client = boto3.client("ssm", region_name=region)
    try:
        client.delete_parameter(Name=param_name)
        click.secho(f"Deleted SSM Parameter: {param_name}", fg="red")
    except Exception as e:
        raise_for_click(f"Failed to delete SSM Parameter {param_name}: {e}")


def delete_log_group(log_group_name, region):
    """Deletes a single CloudWatch Log Group."""
    client = boto3.client("logs", region_name=region)
    try:
        client.delete_log_group(logGroupName=log_group_name)
        click.secho(f"Deleted Log Group: {log_group_name}", fg="red")
    except Exception as e:
        raise_for_click(f"Failed to delete Log Group {log_group_name}: {e}")


def update_lambda_vpc_config(lambda_functions, region):
    """
    Updates Lambda functions to remove their VPC configuration.

    :param lambda_functions: List of Lambda function names to update.
    :param region: AWS region where the Lambda functions are deployed.
    """
    client = boto3.client("lambda", region_name=region)

    for function_name in lambda_functions:
        try:
            client.update_function_configuration(
                FunctionName=function_name,
                VpcConfig={"SubnetIds": [], "SecurityGroupIds": []},
            )
            click.secho(
                f"Updated Lambda function '{function_name}' to remove VPC configuration.",
                fg="yellow",
            )
        except Exception as e:
            click.secho(f"Failed to update Lambda function '{function_name}': {e}")


def remove_ddb_deletion_protection(table_names, region):
    """
    Removes deletion protection from DynamoDB tables.

    :param table_names: List of DynamoDB table names to remove deletion protection from.
    :param region: AWS region where the DynamoDB tables are deployed.
    """
    client = boto3.client("dynamodb", region_name=region)

    for table_name in table_names:
        try:
            client.update_table(TableName=table_name, DeletionProtectionEnabled=False)
            click.secho(
                f"Deletion protection disabled for DynamoDB table '{table_name}'.",
                fg="yellow",
            )
        except Exception as e:
            click.secho(
                f"Failed to disable deletion protection for DynamoDB table '{table_name}': {e}",
                fg="red",
            )


delete_methods = {
    "cloudformation_stacks": delete_cloudformation_stack,
    "s3_buckets": delete_s3_bucket,
    "ecr_repositories": delete_ecr_repository,
    "ssm_params": delete_ssm_param,
    "log_groups": delete_log_group,
}


def delete_resources(resource_dict, region):
    """Map of resource types to their deletion methods, now including SSM Parameters and Log Groups."""

    for resource_type, resources in resource_dict.items():
        delete_method = delete_methods.get(resource_type)
        if delete_method:
            for resource_name in resources:
                delete_method(resource_name, region)
        else:
            click.secho(
                f"No deletion method found for resource type: {resource_type}",
                fg="yellow",
            )


def cleanup_env(
    ctx,
    logger,
    no_confirm=False,
    env_list=None,
):
    # env_name = ctx.obj["ENV_NAME"]
    # env_prefix = ctx.obj["ENV_PREFIX"]
    region = ctx.obj["REGION"]
    account_id = ctx.obj["ACCOUNT_ID"]

    substrings = env_list

    click.secho(f"Cleaning up: {substrings} in {account_id}:{region}", fg="red")

    if click.confirm("Do you want to proceed?", default=False):
        # 1. Gather Resources
        resources = gather_resources(substrings, region)

        # Example for S3 buckets
        if resources["s3_buckets"]:
            click.secho("The following S3 buckets will be emptied", fg="yellow")
            click.secho("\n".join(resources["s3_buckets"]), fg="red")

            # Adjusted condition to check no_confirm flag before calling click.confirm
            if no_confirm or click.confirm(
                "Do you want to proceed with emptying these S3 buckets?", default=False
            ):
                empty_s3_buckets(resources["s3_buckets"], region)
            # else:
            #     ctx.abort()
        else:
            click.secho("No S3 buckets", fg="yellow")

        # 3. Print ECR Repos and confirm
        if resources["ecr_repositories"]:
            click.secho("The following ECR repositories will be emptied:", fg="yellow")
            click.secho("\n".join(resources["ecr_repositories"]), fg="red")
            if no_confirm or click.confirm(
                "Do you want to proceed with emptying these ECR repositories?",
                default=False,
            ):
                empty_ecr_repositories(resources["ecr_repositories"], region)
            # else:
            #     ctx.abort()
        else:
            click.secho("No ECR repositories", fg="yellow")

        if resources["vpc_lambdas"]:
            click.secho(
                "The following Lambda functions will have their VPC configuration removed:",
                fg="yellow",
            )
            click.secho("\n".join(resources["vpc_lambdas"]), fg="red")
            if no_confirm or click.confirm(
                "Do you want to proceed with patching these Lambdas?",
                default=False,
            ):
                update_lambda_vpc_config(resources["vpc_lambdas"], region)
            # else:
            #     ctx.abort()
        else:
            click.secho("No Lambda functions in VPC", fg="yellow")

        if resources["ddb_tables"]:
            click.secho(
                "The following DynamoDB tables will have their deletion protection removed:",
                fg="yellow",
            )
            click.secho("\n".join(resources["ddb_tables"]), fg="red")
            if no_confirm or click.confirm(
                "Do you want to proceed with removing deletion protection from these tables?",
                default=False,
            ):
                remove_ddb_deletion_protection(resources["ddb_tables"], region)
            # else:
            #     ctx.abort()

        # 4. Print CloudFormation Stacks and confirm
        if resources["cloudformation_stacks"]:
            click.secho(
                "The following CloudFormation stacks will be deleted:", fg="yellow"
            )
            click.secho("\n".join(resources["cloudformation_stacks"]), fg="red")
            if no_confirm or click.confirm(
                "Do you want to proceed with deleting these CloudFormation stacks?",
                default=False,
            ):
                delete_resources(
                    {"cloudformation_stacks": resources["cloudformation_stacks"]},
                    region,
                )
            else:
                ctx.abort()
        else:
            click.secho("No CloudFormation stacks", fg="yellow")

        # 5. Gather Unmanaged Resources
        unmanaged_resources = gather_unmanaged_resources(substrings, region)

        # 6. Handle Remaining S3 Buckets
        for resource_type, delete_function in delete_methods.items():
            resources = unmanaged_resources.get(resource_type, [])
            if resources:
                resource_names = "\n".join(resources)
                click.secho(
                    f"The following {resource_type} will be deleted:", fg="yellow"
                )
                click.secho(resource_names, fg="red")

                if no_confirm or click.confirm(
                    f"Do you want to proceed with deleting these {resource_type}?",
                    default=False,
                ):
                    for resource_name in resources:
                        delete_function(resource_name, region)

        click.secho(f"Cleaned up: {substrings}", fg="green")

