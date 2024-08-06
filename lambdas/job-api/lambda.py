import os
import json
import boto3

# env variables
SSM_DOCUMENT_NAME = os.environ["SSM_DOCUMENT_NAME"]
# URL of your SQS queue
SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL_R2EX"]
print("Loading function")
# Load necessary AWS SDK clients
ssm = boto3.client("ssm")
code_pipeline = boto3.client("codepipeline")
sqs_client = boto3.client("sqs")

COMMAND_RUN = "run"
COMMAND_STATUS = "status"

STATUS_FAILED = "FAILED"
STATUS_SUCCESS = "SUCCESS"
STATUS_IN_PROGRESS = "IN PROGRESS"


def lambda_handler(event, context):
    # Log the received event
    print("Received event: " + json.dumps(event, indent=2))

    try:
        # Get parameters from the event
        command = event["command"]

        if command == COMMAND_RUN:
            return run_command(event)
        elif command == COMMAND_STATUS:
            return check_command_status(event)
        else:
            raise Exception("Unknown command")

    except Exception as e:
        print(e)
        raise Exception("Error processing a job")


# create function to extract sqs queue url based on pipeline name
def extract_sqs_url(pipeline):
    try:
        # find which variant name is 'digital-twin' available inside pipeline name
        if pipeline.find("digital-twin") != -1:
            queue = SQS_QUEUE_URL
        else:
            print("SQS Queue URL Not Found")
            queue = ""
        return queue
    except Exception as e:
        print(e)
        return None


def run_command(event):
    # Get parameters from the event
    instance_id = event["instanceId"]
    command_text = event["commandText"]
    command_timeout = event["timeout"]
    command_working_directory = event["workingDirectory"]
    input_bucket_name = event["inputBucketName"]
    input_object_key = event["inputObjectKey"]

    output_artifact_path = event["outputArtifactPath"]
    output_bucket_name = event["outputBucketName"]
    output_object_key = event["outputObjectKey"]

    pipeline_execution_id = event["executionId"]
    pipeline_arn = event["pipelineArn"]
    pipeline_name = event["pipelineName"]

    print("----Start branch name from sqs-----")
    receipt_handle = ""
    get_branch_name = ""
    sqs_queue_url = extract_sqs_url(pipeline_name)
    print("SQS Queue URL: " + sqs_queue_url)
    # Receive message from SQS FIFO queue
    receive_response = sqs_client.receive_message(
        QueueUrl=sqs_queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20,  # Adjust as needed
    )
    print("--1--")
    print(receive_response)
    # Check if messages were received
    if "Messages" in receive_response:
        for i in receive_response["Messages"]:
            print("MessageId: " + i["MessageId"])
            print("ReceiptHandle: " + i["ReceiptHandle"])
            receipt_handle = i["ReceiptHandle"]
            print("Body: " + i["Body"])
            message_body = i["Body"]
            branch_repo_name_split = message_body.split(",")
            get_branch_name = branch_repo_name_split[0]
            get_repo_name = branch_repo_name_split[1]
            print("Branch Name " + get_branch_name)
            print("Repo Name " + get_repo_name)
    else:
        print("No messages received from SQS FIFO queue")
    # Delete the message from the queue
    # sqs_client.delete_message(
    #       QueueUrl=SQS_QUEUE_URL,
    #        ReceiptHandle=receipt_handle
    #    )
    # collect branch and repo name
    branch_var_name = "branch_name"
    branch_var_value = get_branch_name
    repo_var_name = "repository_name"
    repo_var_value = get_repo_name
    print("----End branch name from sqs-----")
    print("----Start repository name from pipeline-----")
    pipeline_response = code_pipeline.get_pipeline(name=pipeline_name)
    if (
        "RepositoryName"
        in pipeline_response["pipeline"]["stages"][0]["actions"][0]["configuration"]
    ):
        repo_name = pipeline_response["pipeline"]["stages"][0]["actions"][0][
            "configuration"
        ]["RepositoryName"]
        print("Repository Name: " + repo_name)
    else:
        print("Repository Name is not available")
        repo_name = ""
        print("Repository Name: " + repo_name)

    print("----End repository name from pipeline-----")

    # Send command to the builder instance
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName=SSM_DOCUMENT_NAME,
        Parameters={
            "inputBucketName": [input_bucket_name],
            "inputObjectKey": [input_object_key],
            "commands": [command_text],
            "executionTimeout": [str(command_timeout)],
            "workingDirectory": [command_working_directory],
            "outputArtifactPath": [output_artifact_path],
            "outputBucketName": [output_bucket_name],
            "outputObjectKey": [output_object_key],
            "executionId": [pipeline_execution_id],
            "pipelineArn": [pipeline_arn],
            "pipelineName": [pipeline_name],
            "branchVarName": [branch_var_name],
            "branchVarValue": [branch_var_value],
            "repoVarName": [repo_var_name],
            "repoVarValue": [repo_var_value],
            #'testtofailpipeline': [demo_var_fail_pipe]
        },
        CloudWatchOutputConfig={"CloudWatchOutputEnabled": True},
    )

    # extract command ID
    command_id = response.get("Command", {}).get("CommandId", "")

    return {"commandId": command_id, "status": STATUS_IN_PROGRESS}


def check_command_status(event):
    # Get parameters from the event
    command_id = event["commandId"]
    instance_id = event["instanceId"]

    response = ssm.list_commands(CommandId=command_id, InstanceId=instance_id)

    commands = response.get("Commands", {})
    if commands:
        command = commands[0]
        aws_status = command["Status"]

        status = STATUS_FAILED
        if aws_status in ["Pending", "InProgress"]:
            status = STATUS_IN_PROGRESS
        elif aws_status in ["Success"]:
            status = STATUS_SUCCESS

        return {"commandId": command_id, "status": status}

    raise Exception("Command is not found.")
