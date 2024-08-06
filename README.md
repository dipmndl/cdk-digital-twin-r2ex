# Introduction 
This page to collect all the information for the DTDJ MCU Build process on Windows.
# Architecture

Until a better place is found, architecture sketches are maintained in the [20231106-Sprint-11a](https://calsonickansei.sharepoint.com/:i:/s/CloudTransformationPrograms-ELSDevOpsELS-CoreTeam/EaKfb6ijZMlIqxg5pjGjPoMBlHk-SUFQj4zROeYYGtuxcg?e=9TBdTB).

# Getting Started
This CDK creates these stacks:

- [CI/CD stack](./stacks/cicd_stack.py) that creates Custom Actions and CodePipeline for build.
- [Event Stack](./stacks/event_stack.py) that creates Role, Event rule and Lambda functions to be triggered (for    Ec2, Step function and State Machine)
  [State Machine stack](./stacks/state_machine_stack.py) that creates step function definition, role, state machine and ssm document.

## Prerequisites

- [Node.js 14](https://github.com/nodesource/distributions/blob/master/README.md) or later
- [Python 3.10.6](https://www.python.org/) or later with [venv](https://docs.python.org/3/library/venv.html)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [AWS CDK Toolkit](https://docs.aws.amazon.com/cdk/v2/guide/cli.html)
- Your workstation configured with your credentials (using `aws configure sso`)

## Bootstrapping

Deploying stacks with the AWS CDK requires dedicated Amazon S3 buckets and other containers to be available to AWS CloudFormation during deployment.
See [bootstrapping](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html) for details.

Run below command only the first time:

```
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

Use `aws sts get-caller-identity` to get the *ACCOUNT-NUMBER*.

## Configure CDK env

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

To activate your virtualenv:

```
$ source .venv/bin/activate 
            or 
$ source .venv/Scripts/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

# Stacks

# Configure stacks env

Stacks use environment variables, ensure to set them using `export` command or `.env` file.

- `CDK_ENV_NAME`: the environment name and/or the project module (eg. `dev`, `mcu-prod`)
- `CDK_ENV_REGION`: region where deploy the stack (eg. `eu-south-1`)
- `CDK_ENV_ACCOUNT`: account where to deploy the stack (eg. `122480973114`)
- `VPC_ID`: the id of the VPC where to deploy the resources
- `PRIVATE_SUBNETS_IDS`: private subnets where to deploy resources separated by ",". If empty PRIVATE_ISOLATED subnets are selected

## cicd-stack

For this stack we use `CDK_ENV_NAME` to identify:

- the custom action name (eg. `Ec2BuildActionType_EC2-CodePipeline-Builder_1`)
- the type of the pipeline (eg. `build`)
- the environment (eg. `dev`, `prod`)

Please keep customized `.env` files (`.env_mcu-dtdj_build_dev`) into the project branch.

- `CUSTOM_ACTIONS_PROVIDER_NAME`: name of the custom action provider (eg. EC2-CodePipeline-Builder(Version: 1))
- `CUSTOM_ACTIONS_PROVIDER_VERSION`: version of the custom action provider (eg. 1, 2 ,3 etc)
- `CUSTOM_ACTIONS_PROVIDER_CATEGORY`: type of the custom action provider (eg. build)
- `SOURCE_REPO`: name of the code commit repository (eg. `custom-action-demo`)
- `SOURCE_BRANCH`: name of the code commit repository branch that trigger pipeline (eg. `main`)
- `PIPELINE_TIMEOUT`: timeout of the build pipeline in minutes (eg. 180)

## event-stack
- `LAMBDA_TIMEOUT`: timeout of the lambda function in secondss (eg. 15)


# Synthesize and Deploy

From directory where `cdk.json` file reside run:

```
$ cdk synth --profile [YOUR_PROFILE_NAME]
```

To deploy all the stacks run:

```
$ cdk deploy --all --region [REGION] --require-approval never --profile [YOUR_PROFILE_NAME]
```

# Destroy

To destroy the stacks run:

```
$ cdk destroy --all --profile [YOUR_PROFILE_NAME]
```

To synth/deploy/destroy one or more stacks specify its name instead of *--all* flag.

# Resources

- [AWS Cloud Development Kit (AWS CDK) v2](https://docs.aws.amazon.com/cdk/v2/guide/home.html)
- [AWS CDK Toolkit (cdk command)](https://docs.aws.amazon.com/cdk/v2/guide/cli.html)

# Upgrade botocore(1.29.58 to 1.29.101) and boto3(1.20.32 to 1.26.101)
$  pip install botocore --upgrade
$  pip install boto3 --upgrade

# To upgrade boto3 version inside Lambda function add layer into it.
create a working folder:

```
$ mkdir lambda_layer
$ cd lambda_layer
$ mkdir python
$ cd python
```
install boto3 sdk:
```
$ pip install boto3 -t ./
```
Compress the working folder:
```
$ cd ..
$ zip -r D:\lamda_layer\python.zip
```
Create bucket in S3:
```
$ aws s3api create-bucket --bucket [BUCKET_NAME] --region [REGION] --create-bucket-configuration LocationConstraint=[REGION]  --profile [YOUR_PROFILE_NAME]
```
Copy the compress file to S3:
```
$ aws s3 cp python.zip s3://[BUCKET_NAME] --profile [YOUR_PROFILE_NAME]
```
Create a layer and attach it to Lambda function:

# Installing and setup AWS Workspace (Ubuntu 22.04 version) based on project requirements .

- [WS PreBuild Automation Script](./helper-scripts/ws_installsoftware.sh)

# Deploying active directory connection stack 
- Follow cdktf-aws-directory-service-farm project folder and check (./cdktf-aws-directory-service-farm/Readme.md) instruction steps.