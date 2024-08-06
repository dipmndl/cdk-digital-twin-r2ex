from aws_cdk import (
    Stack,
    Duration,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_ssm as ssm,
    CfnOutput,
    aws_logs as logs,
)
from constructs import Construct
from dotenv import load_dotenv
import json
import os

load_dotenv()
EC2_STACK_CONFIG_FILE = "./config/ec2-config.json"
EC2_STATEMACHINE_CONFIG_FILE = "./step-functions/definition.json"
REGION = os.environ["CDK_ENV_REGION"]
ACCOUNT_ID = os.environ["CDK_ENV_ACCOUNT"]
CDK_ENV_OS = os.environ["CDK_ENV_OS"]


class StateMachineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        with open(EC2_STACK_CONFIG_FILE, "r") as f:
            ec2s = json.loads(f.read())

        for e in ec2s:
            name = e["name"]
            instance_id = e["instance_id"]

        # Load the JSON file
        with open("./step-functions/definition.json", "r") as file:
            state_machine_definition = json.load(file)

        # Replace placeholders with actual values
        state_machine_definition["States"]["Acquire Builder Flow"]["Branches"][0][
            "States"
        ]["Start EC2 Instance"][
            "Resource"
        ] = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:EC2-{name}-cicd-Instance-api"
        state_machine_definition["States"]["Acquire Builder Flow"]["Branches"][0][
            "States"
        ]["Check Builder Start Status"][
            "Resource"
        ] = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:EC2-{name}-cicd-Instance-api"
        state_machine_definition["States"]["Run Command Flow"]["Branches"][0]["States"][
            "Start Command Execution"
        ][
            "Resource"
        ] = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:EC2-{name}-cicd-Job-api"
        state_machine_definition["States"]["Run Command Flow"]["Branches"][0]["States"][
            "Check Command Status"
        ][
            "Resource"
        ] = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:EC2-{name}-cicd-Job-api"
        # commented for not require auto stop feature
        ''' 
        state_machine_definition["States"]["Release Builder Flow"]["Branches"][0][
            "States"
        ]["Stop EC2 Instance"][
            "Resource"
        ] = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:EC2-{name}-cicd-Instance-api"
        state_machine_definition["States"]["Release Builder Flow"]["Branches"][0][
            "States"
        ]["Check Builder Stop Status"][
            "Resource"
        ] = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:EC2-{name}-cicd-Instance-api"
        '''
        state_machine_definition["States"]["Report Completion"][
            "Resource"
        ] = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:EC2-{name}-cicd-job-completion-handler"

        # over write json file and save it
        with open("./step-functions/definition_updated.json", "w") as file:
            json.dump(state_machine_definition, file, indent=4)

        # step function
        """ step_function_execution_role = iam.Role(
            self, "EC2BuilderStateMachineExecutionRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            path="/",
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaRole')],
        ) """

        # Optionally, you can add inline policies to restrict resources or actions
        """  step_function_execution_role.add_to_policy(
            statement=iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=["*"]  # Modify this to restrict resources as needed
            )
        ) 
        """
        # attach an inline policy to step function role
        inline_policy = iam.Policy(
            self,
            id="Step_Function_Inline_Policy",
            policy_name="StatesExecutionPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=["*"],
                    effect=iam.Effect.ALLOW,
                )
                # Add more statements as needed
            ],
        )
        # ToDo: enable log for statemachine
        # Create a CloudWatch log group
        log_group = logs.LogGroup(
            self,
            id="EC2_" + name + "_StateMachineLogGroup",
            log_group_name="/aws/stepfunctions/" + name + "-StateMachine-Log",
            retention=logs.RetentionDays.ONE_WEEK,  # Adjust retention as neededrm -rf
        )
        # iam policy to access cloudwatch log
        """ log_group_policy = iam.PolicyStatement(
              effect= iam.Effect.ALLOW,
              actions=["logs:*"],
              resources=[log_group.log_group_arn]
        ) """
        step_function_execution_role = iam.Role(
            self,
            id="EC2_" + name + "_Builder_StateMachine_Execution_Role",
            role_name="EC2-" + name + "-State-Machine-Execution-Role",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            path="/",
            managed_policies=[
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    id="EC2_"
                    + name
                    + "_Builder_StateMachine_Execution_Role_Managed_Policy",
                    managed_policy_arn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
                )
            ],
        )
        step_function_execution_role.attach_inline_policy(inline_policy)

        # create state machine using json file
        state_machine = sfn.StateMachine(
            self,
            id="EC2_" + name + "_StateMachineFromJsonFileFor_" + CDK_ENV_OS,
            state_machine_name="EC2-"
            + name
            + "-StateMachineFromJsonFileFor-"
            + CDK_ENV_OS,
            definition_body=sfn.DefinitionBody.from_file(
                "./step-functions/definition_updated.json"
            ),
            # definition_body=sfn.DefinitionBody.from_file(state_machine_definition),
            timeout=Duration.seconds(300),
            state_machine_type=sfn.StateMachineType.STANDARD,
            logs=sfn.LogOptions(destination=log_group, level=sfn.LogLevel.ALL),
            role=step_function_execution_role,
        )

        # Output the statemachine arn
        CfnOutput(
            self,
            "statemachine_arn_r2ex_linux",
            value=state_machine.state_machine_arn,
            export_name="statemachinearnr2exlinux",
        )
        self.statemachinearnr2exlinux = state_machine.state_machine_arn

        # Create SSM Documents
        build_job_document = ssm.CfnDocument(
            self,
            id="EC2-" + name + "-RunBuildJobOnSSMDocumentEc2Instance_" + CDK_ENV_OS,
            name="EC2-" + name + "-RunBuildJobOnSSMDocumentEc2Instance-" + CDK_ENV_OS,
            document_type="Command",
            content={
                "schemaVersion": "2.2",
                "description": "Downloads build artifacts from S3 and runs specified build scripts.",
                "parameters": {
                    "branchVarName": {
                        "default": "",
                        "description": "(Required) Specify the pipeline custom variable name",
                        "type": "String"
                        },
                    "branchVarValue": {
                        "default": "",
                        "description": "(Required) Specify the pipeline custom variable value",
                        "type": "String"
                        },
                    "repoVarName": {
                        "default": "",
                        "description": "(Required) Specify the code commit repository name",
                        "type": "String"
                        },
                    "repoVarValue": {
                        "default": "",
                        "description": "(Required) Specify the code commit repository value",
                        "type": "String"
                        },
                    "inputBucketName": {
                        "description": "(Required) Specify the S3 bucket name of the input artifact.",
                        "type": "String",
                        "default": "",
                    },
                    "inputObjectKey": {
                        "description": "(Required) Specify the S3 objectKey of the input artifact.",
                        "type": "String",
                        "default": "",
                    },
                    "commands": {
                        "description": "(Required) Specify the commands to run or the paths to existing scripts on the instance.",
                        "type": "String",
                        "displayType": "textarea",
                    },
                    "executionId": {
                        "description": "(Required) Specify the pipeline execution ID",
                        "type": "String",
                        "default": "",
                    },
                    "pipelineArn": {
                        "description": "(Required) Specify the pipeline ARN",
                        "type": "String",
                        "default": "",
                    },
                    "pipelineName": {
                        "description": "(Required) Specify the pipeline Name",
                        "type": "String",
                        "default": "",
                    },
                    "workingDirectory": {
                        "type": "String",
                        "default": "",
                        "description": "(Optional) The path where the content will be downloaded and executed from on your instance.",
                    },
                    "outputArtifactPath": {
                        "type": "String",
                        "default": "",
                        "description": "(Optional) The path of the output artifact to upload to S3.",
                    },
                    "outputBucketName": {
                        "description": "(Optional) Specify the S3 bucket name of the output artifact.",
                        "type": "String",
                        "default": "",
                    },
                    "outputObjectKey": {
                        "description": "(Optional) Specify the S3 objectKey of the output artifact.",
                        "type": "String",
                        "default": "",
                    },
                    "executionTimeout": {
                        "description": "(Optional) The time in seconds for a command to complete before it is considered to have failed. Default is 3600 (1 hour). Maximum is 28800 (8 hours).",
                        "type": "String",
                        "default": "3600",
                        "allowedPattern": "([1-9][0-9]{0,3})|(1[0-9]{1,4})|(2[0-7][0-9]{1,3})|(28[0-7][0-9]{1,2})|(28800)",
                    },
                },
                "mainSteps": [
                    {
                        "name": "linux_script",
                        "precondition": {
                            "StringEquals": [
                                "platformType", "Linux"]},
                        "action": "aws:runShellScript",
                        "inputs": {
                            "runCommand": [
                                "pwd",
                                "echo \"Welcome to R2EX Build....\"", 
                                "echo \"Branch Name: {{branchVarValue}}\"",
                                "echo \"Repo Name: {{repoVarValue}}\""
                                
                            ],
                            "workingDirectory": "{{ workingDirectory }}",
                            "timeoutSeconds": "{{ executionTimeout }}",
                        },
                    }
                ],
            },
        )
        # output of the ssm document
        CfnOutput(
            self,
            "ssm-name",
            value=build_job_document.name,
            export_name="ssm-document-r2ex-linux",
        )
        self.build_job_document = build_job_document.name
