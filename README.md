# Overview
Supporting code for [Automate deletion of AWS CloudFormation stacks and associated resources](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/automate-deletion-cloudformation-stacks-associated-resources.html).

This is a sample Python command line interface, `cfncli`, that demonstrates how the concepts explained in the above pattern for cleaning up CloudFormation Stacks and associated resources can be practically used. See docs below on how to use.

> This is sample code, for non-production usage. You should work with your security and legal teams to meet your organizational security, regulatory and compliance requirements before deployment.

# Prerequisites
- Python 3.13 or later
- [pipx](https://pipx.pypa.io/stable/how-to/install-pipx.html)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html), [configured](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html) with credentials for a non-production account

The commands in this README and `cfncli` use these credentials to create and delete the sample resources. When you use `cfncli` on your own stacks, the credentials also need permission to delete the resources in those stacks, because CloudFormation [uses your credentials](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-iam-servicerole.html) for stack operations unless the stack has a service role.

Install Poetry:
```bash
pipx install poetry==2.5.1
```

Install `cfncli` and its dependencies, then activate the virtual environment so that `cfncli` is on your PATH:
```bash
poetry install
eval $(poetry env activate)
cfncli --help
```

All commands have help text, so you can run `cfncli --help` to see all available commands.

## Deploy a sample cloudformation stack and unmanaged resources
```bash 
aws cloudformation create-stack \
  --stack-name sampleforcleanup-Stack\
  --template-body file://samples/sample-cfn-stack.yaml \
  --parameters ParameterKey=VpcId,ParameterValue=vpc-<> \
  --region us-east-1
  ```
```bash 
aws ssm put-parameter \
    --name "/sampleforcleanup/database/password" \
    --value "your_db_password" \
    --type "SecureString" \
    --description "Database password for my app" \
    --tier "Standard" \
    --region "us-east-1"
```
```bash 
aws s3api create-bucket \
    --bucket sampleforcleanup-unmanagedbucket-<REGION>-<ACCOUNT_ID> \
    --region us-east-1
```
Replace `<REGION>` and `<ACCOUNT_ID>` with your AWS Region and account ID.

## Command to start clean up
```
cfncli -r us-east-1  dev cleanup-env  --prefix-list sampleforcleanup 
```

S3 delivers server access logs [on a best-effort basis, usually within a few hours](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ServerLogs.html). If a log arrives in `sampleforcleanup-access-logs-<REGION>-<ACCOUNT_ID>` after `cfncli` empties it, the stack deletion fails because the bucket is not empty. Run the command again: `cfncli` selects the stack in `DELETE_FAILED` status, empties the bucket again, and retries the deletion.

## Sample output
```
cfncli -r us-east-1 dev cleanup-env --prefix-list sampleforcleanup
Cleaning up: ['sampleforcleanup'] in <ACCOUNT_ID>:us-east-1
Do you want to proceed? [y/N]: y
The following S3 buckets will be emptied
sampleforcleanup-access-logs-us-east-1-<ACCOUNT_ID>
sampleforcleanup-unmanagedbucket-us-east-1-<ACCOUNT_ID>
Do you want to proceed with emptying these S3 buckets? [y/N]: y
Emptied S3 bucket: sampleforcleanup-access-logs-us-east-1-<ACCOUNT_ID>
Emptied S3 bucket: sampleforcleanup-unmanagedbucket-us-east-1-<ACCOUNT_ID>
No ECR repositories
No Lambda functions in VPC
The following DynamoDB tables will have their deletion protection removed:
sampleforcleanup-MyDynamoDBTable-us-east-1-<ACCOUNT_ID>
Do you want to proceed with removing deletion protection from these tables? [y/N]: y
Deletion protection disabled for DynamoDB table 'sampleforcleanup-MyDynamoDBTable-us-east-1-<ACCOUNT_ID>'.
The following CloudFormation stacks will be deleted:
sampleforcleanup-Stack
Do you want to proceed with deleting these CloudFormation stacks? [y/N]: y
Initiated deletion of CloudFormation stack: sampleforcleanup-Stack
Waiting for stack sampleforcleanup-Stack to be deleted...
CloudFormation stack sampleforcleanup-Stack deleted successfully.
The following s3_buckets will be deleted:
sampleforcleanup-unmanagedbucket-us-east-1-<ACCOUNT_ID>
Do you want to proceed with deleting these s3_buckets? [y/N]: y
Deleted S3 bucket: sampleforcleanup-unmanagedbucket-us-east-1-<ACCOUNT_ID>
The following ssm_params will be deleted:
/sampleforcleanup/database/password
Do you want to proceed with deleting these ssm_params? [y/N]: y
Deleted SSM Parameter: /sampleforcleanup/database/password
Cleaned up: ['sampleforcleanup']
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

