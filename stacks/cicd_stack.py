from aws_cdk import (
    Aws,
    Duration,
    Stack,
    aws_ec2 as ec2,
    aws_codecommit as codecommit,
    aws_codepipeline as codepipeline,
    aws_iam as iam,
    aws_codepipeline_actions as codepipeline_actions
)
from constructs import Construct
from dotenv import load_dotenv
import os
import json

load_dotenv()

EC2_STACK_CONFIG_FILE = "./config/ec2-config.json"
VPC_ID = os.environ["VPC_ID"]
PRIVATE_SUBNETS_IDS = (
    os.environ["PRIVATE_SUBNETS_IDS"].strip().split(",")
    if len(os.environ["PRIVATE_SUBNETS_IDS"]) > 0
    else None
)
SOURCE_REPO = os.environ["SOURCE_REPO"]
SOURCE_BRANCH = os.environ["SOURCE_BRANCH"]
PIPELINE_TIMEOUT = int(os.environ["PIPELINE_TIMEOUT"])
REGION = os.environ["CDK_ENV_REGION"]
PROVIDER_NAME = os.environ["CUSTOM_ACTIONS_PROVIDER_NAME"]
PROVIDER_VERSION = os.environ["CUSTOM_ACTIONS_PROVIDER_VERSION"]


class CicdStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, ssmDocumentname: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_lookup(self, "vpc", vpc_id=VPC_ID)
        if not vpc:
            print("Failed finding VPC {}".format(VPC_ID))
            return

        with open(EC2_STACK_CONFIG_FILE, "r") as f:
            ec2s = json.loads(f.read())

        for e in ec2s:
            name = e["name"]

        repository = codecommit.Repository(
            self, "SourceRepo", repository_name=SOURCE_REPO
        )

        # source output
        source_artifact = codepipeline.Artifact("SourceArtifact")

        # source action
        source = codepipeline_actions.CodeCommitSourceAction(
            action_name="SourceAction",
            repository=repository,
            branch=SOURCE_BRANCH,
            output=source_artifact,
            trigger=codepipeline_actions.CodeCommitTrigger.EVENTS,
        )

        # source stage
        source_stage = codepipeline.StageProps(
            stage_name="SourceStage", actions=[source]
        )

        # Make a custom CodePipeline Action
        custom_actions = codepipeline.CustomActionRegistration(
            self,
            id="Ec2BuildActionType_" + PROVIDER_NAME + "_" + PROVIDER_VERSION,
            category=codepipeline.ActionCategory.BUILD,
            artifact_bounds=codepipeline.ActionArtifactBounds(
                min_inputs=0, max_inputs=1, min_outputs=0, max_outputs=1
            ),
            provider=PROVIDER_NAME,
            version=PROVIDER_VERSION,  # change to 1 first time deployment.
            # entity_url="https://ap-south-1.console.aws.amazon.com/systems-manager/documents/${"+build_job_ssmdocument.name+"}", # --> refer ssm document type
            entity_url=f"https://{REGION}.console.aws.amazon.com/systems-manager/documents/{ssmDocumentname}",
            execution_url=f"https://{REGION}.console.aws.amazon.com/states/home?region={REGION}#/executions/details/{{ExternalExecutionId}}",
            action_properties=[
                codepipeline.CustomActionProperty(
                    name="ImageId",
                    description="AMI to use for EC2 build instances.",
                    key=True,
                    required=True,
                    secret=False,
                    queryable=False,
                    type="String",
                ),
                codepipeline.CustomActionProperty(
                    name="InstanceType",
                    description="Instance type for EC2 build instances.",
                    key=True,
                    required=True,
                    secret=False,
                    queryable=False,
                    type="String",
                ),
                codepipeline.CustomActionProperty(
                    name="Command",
                    description="Command(s) to execute.",
                    key=True,
                    required=True,
                    secret=False,
                    queryable=False,
                    type="String",
                ),
                codepipeline.CustomActionProperty(
                    name="WorkingDirectory",
                    description="Working directory for the command to execute.",
                    key=True,
                    required=False,
                    secret=False,
                    queryable=False,
                    type="String",
                ),
                codepipeline.CustomActionProperty(
                    name="OutputArtifactPath",
                    description="Path of the file(-s) or directory(-es) to use as custom action output artifact.",
                    key=True,
                    required=False,
                    secret=False,
                    queryable=False,
                    type="String",
                ),
            ],
        )

        # Create an IAM role for CodePipeline
        codepipeline_role = iam.Role(
            self,
            id="EC2_" + name + "_cicd_linux_pipeline_Role",
            role_name="EC2-" + name + "-cicd-linux-pipeline-Role",
            assumed_by=iam.ServicePrincipal("codepipeline.amazonaws.com"),
            description="IAM role for SOC CodePipeline",
            managed_policies=[
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    id="EC2_CodePipeline_Full_Access_Role_Managed_Policy",
                    managed_policy_arn="arn:aws:iam::aws:policy/AWSCodePipeline_FullAccess",
                ),
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    id="EC2_CodeCommit_Full_Access_Role_Managed_Policy",
                    managed_policy_arn="arn:aws:iam::aws:policy/AWSCodeCommitFullAccess",
                ),
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    id="EC2_S3_Full_Access_Role_Managed_Policy",
                    managed_policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
                ),
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    id="EC2_PipelineCustomActions_Access_Role_Managed_Policy",
                    managed_policy_arn="arn:aws:iam::aws:policy/AWSCodePipelineCustomActionAccess",
                ),
            ],
        )
