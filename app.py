#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.cicd_stack import CicdStack
from stacks.event_stack import EventStack
from stacks.state_machine_stack import StateMachineStack
from stacks.sqs_stack import SqsStack
from dotenv import load_dotenv
import os
import sys

load_dotenv()

if "CDK_ENV_NAME" not in os.environ:
    print("CDK_ENV_NAME unspecified. Exiting")
    sys.exit(0)
else:
    print(
        f'Working with "{os.environ["CDK_ENV_NAME"]}" environment (region:{os.environ["CDK_ENV_REGION"]} account:{os.environ["CDK_ENV_ACCOUNT"]})'
    )

cdk_env = cdk.Environment(
    account=os.environ["CDK_ENV_ACCOUNT"], region=os.environ["CDK_ENV_REGION"]
)
CDK_ENV_OS = os.environ["CDK_ENV_OS"].lower()

app = cdk.App()

state_machine_stack = StateMachineStack(
    app,
    "state-machine-stack-" + os.environ["CDK_ENV_NAME"] + "-" + CDK_ENV_OS,
    env=cdk_env,
)
cicd_stack = CicdStack(
    app,
    "cicd-stack-" + os.environ["CDK_ENV_NAME"] + "-" + CDK_ENV_OS,
    env=cdk_env,
    ssmDocumentname=state_machine_stack.build_job_document,
)
sqs_stack = SqsStack(
    app, "sqs-stack-" + os.environ["CDK_ENV_NAME"] + "-" + CDK_ENV_OS, env=cdk_env
)

event_stack = EventStack(
    app,
    "event-stack-" + os.environ["CDK_ENV_NAME"] + "-" + CDK_ENV_OS,
    env=cdk_env,
    statemachine_arn=state_machine_stack.statemachinearnr2exlinux,
    ssmDocumentname=state_machine_stack.build_job_document,
    sqs_urls=sqs_stack.sqsurls,
)


app.synth()
