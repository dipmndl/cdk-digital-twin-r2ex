from aws_cdk import (
    Stack,
    Duration,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as lambda_,
    aws_sqs as sqs,
    aws_codepipeline as codepipeline,
    CfnOutput,
)
from constructs import Construct
from dotenv import load_dotenv
import json
import os

load_dotenv()

EC2_STACK_CONFIG_FILE = "./config/ec2-config.json"
REGION = os.environ["CDK_ENV_REGION"]
ACCOUNT = os.environ["CDK_ENV_ACCOUNT"]
PROVIDER_NAME = os.environ["CUSTOM_ACTIONS_PROVIDER_NAME"]
PROVIDER_VERSION = os.environ["CUSTOM_ACTIONS_PROVIDER_VERSION"]
PROVIDER_CATEGORY = os.environ["CUSTOM_ACTIONS_PROVIDER_CATEGORY"]
LAMBDA_TIMEOUT = int(os.environ["LAMBDA_TIMEOUT"])
BRANCH_KEY = os.environ["BRANCH_KEY"]
REPO_NAME = os.environ["REPO_NAME"]
REPO_ID = os.environ["REPO_ID"]
REPO_ARN = os.environ["REPO_ARN"]
PIPELINE_NAME = os.environ["PIPELINE_NAME"]
PIPELINE_NAME_ARN = os.environ["PIPELINE_NAME_ARN"]
CC_RECIPIENT_EMAIL = os.environ["CC_RECIPIENT_EMAIL"]
S3_BUCKET = os.environ["S3_BUCKET"]
SECRET_MANAGER_ARN_GRAPH_API = os.environ["SECRET_MANAGER_ARN_GRAPH_API"]
SENDER_EMAIL = os.environ["SENDER_EMAIL"]


class EventStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        statemachine_arn: str,
        ssmDocumentname: str,
        sqs_urls: list,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        with open(EC2_STACK_CONFIG_FILE, "r") as f:
            ec2s = json.loads(f.read())

        for e in ec2s:
            name = e["name"]
            instance_id = e["instance_id"]

        # AWS Lambda Basic Execution Role
        lambda_basic_execution_role = iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AWSLambdaBasicExecutionRole"
        )

        # IAM Roles and Policies

        # Job Completion Handler Execution Role
        job_completion_handler_execution_role = iam.Role(
            self,
            id="EC2_" + name + "_cicd-JobCompletionHandlerExecutionRole",
            role_name="EC2-" + name + "-cicd-JobCompletionHandlerExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[lambda_basic_execution_role],
        )

        # CodePipeline Poller Execution Role
        codepipeline_poller_execution_role = iam.Role(
            self,
            id="EC2_" + name + "_cicd-CodePipelinePollerExecutionRole",
            role_name="EC2-" + name + "-cicd-CodePipelinePollerExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[lambda_basic_execution_role],
            inline_policies={
                "root": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "codepipeline:PollForJobs",
                                "codepipeline:GetJobDetails",
                                "codepipeline:AcknowledgeJob",
                                "codepipeline:PutJobSuccessResult",
                                "codepipeline:PutJobFailureResult",
                            ],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "states:DescribeExecution",
                                "states:StartExecution",
                            ],
                            resources=["*"],
                        ),
                    ]
                )
            },
        )
        # EC2 Role
        ec2_builder_role = iam.Role(
            self,
            id="EC2_" + name + "_cicd-Ec2BuilderRole",
            role_name="EC2-" + name + "-cicd-Ec2BuilderRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonEC2RoleforSSM"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonEC2ContainerRegistryPowerUser"
                ),
                # iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
            ],
        )
        ec2_builder_role_arn = ec2_builder_role.role_arn
        # Instance API Execution Role
        instance_api_execution_role = iam.Role(
            self,
            id="EC2_" + name + "_cicd-InstanceApiExecutionRole",
            role_name="EC2-" + name + "-cicd-InstanceApiExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[lambda_basic_execution_role],
            inline_policies={
                "root": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["iam:PassRole"], resources=[ec2_builder_role_arn]
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "ec2:CreateTags",
                                "ec2:RunInstances",
                                "ec2:TerminateInstances",
                                "ec2:DescribeInstances",
                                "ec2:DescribeInstanceStatus",
                                "ec2:Start*",
                                "ec2:Stop*",
                                "ssm:DescribeInstanceInformation",
                            ],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            actions=["ssm:DescribeInstanceInformation"], resources=["*"]
                        ),
                    ]
                )
            },
        )

        # Job API Execution Role
        job_api_execution_role = iam.Role(
            self,
            id="EC2_" + name + "_cicd-JobApiExecutionRole",
            role_name="EC2-" + name + "-cicd-JobApiExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[lambda_basic_execution_role],
            inline_policies={
                "root": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "ssm:SendCommand",
                                "ssm:ListCommands",
                                "sqs:GetQueueAttributes",
                                "sqs:GetQueueUrl",
                                "sqs:ReceiveMessage",
                                "sqs:DeleteMessage",
                                "sqs:SendMessage",
                                "codepipeline:ListPipelineExecutions",
                                "codepipeline:ListPipelines",
                                "codepipeline:GetPipeline",
                                "codepipeline:GetPipelineExecution",
                                "codepipeline:GetPipelineState",
                            ],
                            resources=["*"],
                            effect=iam.Effect.ALLOW,
                        ),
                    ]
                )
            },
        )

        # ToDo: Create an IAM Instance Profile and associate it with the IAM Role
        instance_profile = iam.CfnInstanceProfile(
            self,
            id="EC2_" + name + "_cicd-InstanceProfile",
            instance_profile_name="EC2-" + name + "-cicd-InstanceProfile",
            roles=[ec2_builder_role.role_name],
        )

        # Output the ARN of the IAM Instance Profile
        instance_profile_arn = instance_profile.attr_arn
        instance_profile_arn_output = CfnOutput(
            self,
            id="EC2_" + name + "_cicd-InstanceProfileArn",
            value=instance_profile_arn,
            export_name="InstanceProfileArnlinux",
        )

        # Create SQS, code pipeline, Lambda and log access role
        lambda_trigger_pipeline_execution_role = (iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSQSFullAccess"))
        lambda_trigger_pipeline_execution_role = (iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodePipeline_FullAccess") )
        lambda_trigger_pipeline_execution_role = (iam.ManagedPolicy.from_aws_managed_policy_name("AWSLambda_FullAccess"))
        branch_trigeer_pipeline_execution_role = iam.Role(
            self,
            id="EC2_" + name + "_cicd-trigeer_pipeline_execution_role",
            role_name="EC2-" + name + "-cicd-trigeer-pipeline-execution-role",
            description="Role with full access to SQS, CodePipeline, Lambda, and CloudWatch Logs",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[lambda_trigger_pipeline_execution_role],
            inline_policies={
                "log_access": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["logs:*"],
                            resources=["*"],
                            effect=iam.Effect.ALLOW,
                        ),
                    ]
                )
            },
        )

        # Create S3, SQS, CodeCommit, CodePipeline, Lambda, Cloudwatchlog, Secretmanager access role
        mail_trigger_execution_role = iam.Role(
            self,
            id="EC2_" + name + "_cicd-mail_trigger_execution_role",
            role_name="EC2-" + name + "-cicd-mail-trigger-execution-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role with full access to S3, SQS, CodeCommit, CodePipeline, Lambda, CloudWatch Logs, and SecretManager to trigger mail",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSQSFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeCommitFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodePipeline_FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSLambda_FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("SecretsManagerReadWrite"),
            ],
        )
        # Define a Dead Letter Queue
        dlq = sqs.Queue(
            self, "LambdaDLQ",
            encryption=sqs.QueueEncryption.SQS_MANAGED  # Optional: specify encryption settings for the DLQ
        )
        # call lambda fuctions
        # Define the JobCompletionHandler Lambda function
        job_completion_handler = lambda_.Function(
            self,
            id="EC2_" + name + "_cicd_job_completion_handler",
            function_name="EC2-" + name + "-cicd-job-completion-handler",
            description="Handles result of job flow execution.",
            code=lambda_.Code.from_asset("lambdas/job-completion-handler"),
            handler="lambda.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            role=job_completion_handler_execution_role,
            memory_size=128,
            timeout=Duration.seconds(LAMBDA_TIMEOUT),
            tracing=lambda_.Tracing.ACTIVE,
            dead_letter_queue= dlq
        )
        
        # Define the InstanceApi Lambda function
        instance_api = lambda_.Function(
            self,
            id="EC2_" + name + "_cicd_Instance_api",
            function_name="EC2-" + name + "-cicd-Instance-api",
            description="Manages EC2 instances that carry out custom action jobs.",
            code=lambda_.Code.from_asset("lambdas/instance-api"),
            handler="lambda.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            role=instance_api_execution_role,
            memory_size=128,
            timeout=Duration.seconds(LAMBDA_TIMEOUT),
            environment={
                "BUILDER_INSTANCE_PROFILE_ARN": instance_profile_arn,
                "INSTANCE_ID": instance_id,
            },
            tracing=lambda_.Tracing.ACTIVE,
            dead_letter_queue= dlq
        
        )

        # Define the JobApi Lambda function
        job_api = lambda_.Function(
            self,
            id="EC2_" + name + "_cicd_Job_api",
            function_name="EC2-" + name + "-cicd-Job-api",
            description="Runs and tracks SSM commands on EC2 instances.",
            code=lambda_.Code.from_asset("lambdas/job-api"),
            handler="lambda.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            role=job_api_execution_role,
            memory_size=128,
            timeout=Duration.seconds(LAMBDA_TIMEOUT),
            environment={
                "SSM_DOCUMENT_NAME": ssmDocumentname,
                "SQS_QUEUE_URL_R2EX": sqs_urls[0],
            },
            tracing=lambda_.Tracing.ACTIVE,
            dead_letter_queue= dlq
           
        )

        # Define the pollar Lambda function
        code_pipeline_poller_lambda = lambda_.Function(
            self,
            id="EC2_" + name + "_cicd_code_pipeline_poller",
            function_name="EC2-" + name + "-cicd-code-pipeline-poller",
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambdas/poller"),
            role=codepipeline_poller_execution_role,
            handler="lambda.lambda_handler",
            description="Polls CodePipeline for Custom Actions",
            memory_size=128,
            timeout=Duration.seconds(LAMBDA_TIMEOUT),
            environment={
                "STATE_MACHINE_ARN": statemachine_arn,
                "CUSTOM_ACTION_PROVIDER_NAME": PROVIDER_NAME,
                "CUSTOM_ACTION_PROVIDER_CATEGORY": PROVIDER_CATEGORY,
                "CUSTOM_ACTION_PROVIDER_VERSION": PROVIDER_VERSION,
            },
            tracing=lambda_.Tracing.ACTIVE,
            dead_letter_queue= dlq
           
        )

        # Define the branch trigger pipeline Lambda function
        branch_trigger_pipeline_lambda = lambda_.Function(
            self,
            id="EC2_" + name + "_branch_trigger_pipeline",
            function_name="EC2-" + name + "-branch-trigger-pipeline",
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambdas/branch-trigger-pipeline"),
            role=branch_trigeer_pipeline_execution_role,
            handler="lambda.lambda_handler",
            description="Triggers CodePipeline for Code Commit branch state change",
            memory_size=128,
            timeout=Duration.seconds(LAMBDA_TIMEOUT),
            environment={
                "BRANCH_KEY": BRANCH_KEY,
                "PIPELINE_NAME": PIPELINE_NAME,
                "SQS_QUEUE_URL_R2EX": sqs_urls[0],
            },
            tracing=lambda_.Tracing.ACTIVE,
            dead_letter_queue= dlq
            
        )

        # Define the trigger pipeline Lambda function
        mail_trigger_pipeline_lambda = lambda_.Function(
            self,
            id="EC2_" + name + "_trigger_mail",
            function_name="EC2-" + name + "-trigger-mail",
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambdas/trigger-mail"),
            role=mail_trigger_execution_role,
            handler="lambda.lambda_handler",
            description="Trigger mail after code pipeline execution state change",
            memory_size=128,
            timeout=Duration.seconds(LAMBDA_TIMEOUT),
            environment={
                "CC_RECIPIENT_EMAIL": CC_RECIPIENT_EMAIL,
                "S3_BUCKET": S3_BUCKET,
                "SECRET_MANAGER_ARN_GRAPH_API": SECRET_MANAGER_ARN_GRAPH_API,
                "SENDER_EMAIL": SENDER_EMAIL,
                "SQS_QUEUE_URL_R2EX": sqs_urls[0],
            },
            tracing=lambda_.Tracing.ACTIVE,
            dead_letter_queue= dlq
            
        )

        # CloudWatch Event Rule for CodePipeline Action Started Event
        code_pipeline_action_rule = events.Rule(
            self,
            id="EC2_" + name + "_cicd-CodePipelineActionStartedEvent",
            rule_name="EC2-" + name + "-cicd-CodePipelineActionStartedEvent",
            description="Rule for Digital Twin r2ex linux integration CodePipeline action started event",
            event_pattern={
                "source": ["aws.codepipeline"],
                "detail": {"state": ["STARTED"]},
            },
        )
        code_pipeline_action_rule.add_target(
            targets.LambdaFunction(code_pipeline_poller_lambda)
        )

        # CloudWatch Event Rule for Scheduled Event
        check_code_pipeline_scheduled_rule = events.Rule(
            self,
            id="EC2_" + name + "_cicd-CheckCodePipelineScheduledEvent",
            rule_name="EC2-" + name + "-cicd-CheckCodePipelineScheduledEvent",
            description="Rule for Digital Twin r2ex linux integration scheduled event",
            schedule=events.Schedule.rate(Duration.minutes(1)),
        )
        check_code_pipeline_scheduled_rule.add_target(
            targets.LambdaFunction(code_pipeline_poller_lambda)
        )

        # Cloudwatch Event Rule for CodeCommit Branch State Change
        code_commit_branch_state_change_rule = events.Rule(
            self,
            id="EC2_" + name + "_cicd-CodeCommitBranchStateChangeEvent",
            rule_name="EC2-" + name + "-cicd-CodeCommitBranchStateChangeEvent",
            description="Rule for Digital Twin r2ex linux integration CodeCommit branch state change event",
            event_pattern={
                "source": ["aws.codecommit"],
                "detail_type": ["CodeCommit Repository State Change"],
                "resources": [REPO_ARN],
                "detail": {
                    "event": ["referenceUpdated"],
                    "repositoryName": [REPO_NAME],
                    "repositoryId": [REPO_ID],
                },
            },
            targets=[targets.LambdaFunction(branch_trigger_pipeline_lambda)],
        )

        # Cloudwatch Event Rule for CodePipeline Execution State Change
        code_pipeline_execution_state_change_rule = events.Rule(
            self,
            id="EC2_" + name + "_cicd-CodePipelineExecutionStateChangeEvent",
            rule_name="EC2-" + name + "-cicd-CodePipelineExecutionStateChangeEvent",
            description="Rule for Digital Twin r2ex linux integration CodePipeline execution state change event",
            event_pattern={
                "source": ["aws.codepipeline"],
                "detail_type": ["CodePipeline Pipeline Execution State Change"],
                "resources": [PIPELINE_NAME_ARN],
                "detail": {
                    "pipeline": [PIPELINE_NAME_ARN],
                    "state": ["SUCCEEDED", "FAILED", "CANCELED", "SUPERSEDED"],
                },
            },
            targets=[targets.LambdaFunction(mail_trigger_pipeline_lambda)],
        )
