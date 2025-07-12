# Overview
Supporting code for [Automate deletion of AWS CloudFormation stacks and associated resources](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/automate-deletion-cloudformation-stacks-associated-resources.html).

This is a reference implementation of a Python CLI tool called `cfncli` utility to demonstrate how the concepts explained in the above pattern for cleaning up CloudFormation Stacks and associated resources can be practically used. See docs below on how to use.

# Pre-requisite:
Install poetry
```
pip install poetry
```
For installing cfncli,

```bash
poetry install
```

This will install the `cfncli` CLI along with any other project dependencies. All commands have help text, so you can run `cfncli --help` to see all available commands.

## Deploy a sample cloudformation stack and a ssm-parameter to test the cfncli functionality 
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
    --bucket samplesorcleanup-unmanagedbucket-<REGION>-<ACCOUNT ID> \
    --region us-east-1
```

## Command to start clean up
```
cfncli -r us-east-1  dev cleanup-env  --prefix-list sampleforcleanup 
```

## Sample Ouptut
```
cfncli --region us-east-1  dev cleanup-env --prefix-list sampleforcleanup
Cleaning up: ['sampleforcleanup'] in xxxxxxxxxx:us-east-1
Do you want to proceed? [Y/n]: Y
No S3 buckets
No ECR repositories
No Lambda functions in VPC
The following DynamoDB tables will have their deletion protection removed:
sampleforcleanup-MyDynamoDBTable
Do you want to proceed with removing deletion protection from these tables? [Y/n]: Y
Deletion protection disabled for DynamoDB table 'sampleforcleanup-MyDynamoDBTable'.
The following CloudFormation stacks will be deleted:
sampleforcleanup-Stack
Do you want to proceed with deleting these CloudFormation stacks? [Y/n]: Y
Initiated deletion of CloudFormation stack: sampleforcleanup-Stack
Waiting for stack sampleforcleanup-Stack to be deleted...
CloudFormation stack sampleforcleanup-Stack deleted successfully.
The following ssm_params will be deleted:
/sampleforcleanup/database/password
Do you want to proceed with deleting these ssm_params? [Y/n]: Y
Deleted SSM Parameter: /sampleforcleanup/database/password
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

