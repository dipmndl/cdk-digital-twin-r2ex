import os
import json
import base64
import boto3
import requests
import re
import zipfile
from requests.auth import HTTPBasicAuth
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, timezone

# branch_name = os.environ["BRANCH_NAME"]
sender = os.environ["SENDER_EMAIL"]
cc_recipients = os.environ["CC_RECIPIENT_EMAIL"].split(",")
BUCKET_NAME = os.environ["S3_BUCKET"]
SECRET_MANAGER_ARN_GRAPH_API = os.environ["SECRET_MANAGER_ARN_GRAPH_API"]
# URL of your SQS queue
SQS_QUEUE_URL_R2EX = os.environ["SQS_QUEUE_URL_R2EX"]

code_commit = boto3.client("codecommit")
client_Sec = boto3.client("secretsmanager")
codepipeline = boto3.client("codepipeline")
s3 = boto3.client("s3")
sqs_client = boto3.client("sqs")

response_sec = client_Sec.get_secret_value(SecretId=SECRET_MANAGER_ARN_GRAPH_API)
secret_value = response_sec["SecretString"]
secret_json = json.loads(secret_value)
tenant_id = secret_json["TENANT_ID"]
client_id = secret_json["CLIENT_ID"]
client_secret = secret_json["CLIENT_SECRET"]

attachments = []
recipient = None


def obtain_access_token(tenant_id, client_id, client_secret):
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        # Handle token request errors
        return None


def generate_presigned_url(bucket_name, object_key, expiration=5 * 24 * 60 * 60):

    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": object_key},
        ExpiresIn=expiration,
    )
    return presigned_url


def send_email(
    access_token, sender, recipient, cc_recipient, subject, body, attachments
):
    try:
        print("-----inside mail block------")
        url = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        # Read attachment file in base64 format
        message = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body},
                "toRecipients": [{"emailAddress": {"address": recipient}}],
                "ccRecipients": [
                    {"emailAddress": {"address": cc_recipient}}
                    for cc_recipient in cc_recipients
                ],
                "from": {"emailAddress": {"address": sender}},
                "attachments": [],
            },
            "saveToSentItems": "false",
        }
        # print('---message---')
        # print(message)
        response = requests.post(url, headers=headers, json=message)
        print("--sending mail--")
        print(response)
        if response.status_code != 202:
            # Handle sending email errors
            print(f"Error sending email: {response.status_code}: {response.text}")

    except Exception as e:
        print(f"Error sending email: {e}")


def extract_variant(branch):
    pattern = r"(DT12|dj12|dt7|dj7)"
    match = re.search(pattern, branch, re.IGNORECASE)
    if match:
        return match.group().upper()
    else:
        raise ValueError("Variant not found in branch name.")


# create function to extract sqs queue url based on pipeline name
def extract_sqs_url(pipeline):
    try:
        # find variant name 'digital-twin' is available inside pipeline name
        if pipeline.find("digital-twin") != -1:
            queue = SQS_QUEUE_URL_R2EX
        else:
            print("SQS Queue URL Not Found")
            queue = ""
        return queue
    except Exception as e:
        print(e)
        return None


# create a function to extract branch name, repo name and commit id from sqs
def extract_from_sqs(url):
    try:
        # Receive message from SQS FIFO queue
        receive_response = sqs_client.receive_message(
            QueueUrl=url, MaxNumberOfMessages=1, WaitTimeSeconds=20  # Adjust as needed
        )
        print("--1--")
        print(receive_response)
        # Check if messages were received
        if "Messages" in receive_response:
            for i in receive_response["Messages"]:
                print("MessageId: " + i["MessageId"])
                print("ReceiptHandle: " + i["ReceiptHandle"])
                get_receipt_handle = i["ReceiptHandle"]
                print("Body: " + i["Body"])
                message_body = i["Body"]
                branch_repo_commitid_split = message_body.split(",")
                get_branch_name = branch_repo_commitid_split[0]
                get_repo_name = branch_repo_commitid_split[1]
                get_commit_id = branch_repo_commitid_split[2]
                # print('Branch Name '+get_branch_name)
                # print('Repo Name '+get_repo_name)
                # print('Commit ID '+get_commit_id)
        else:
            print("No messages received from SQS FIFO queue")
        return get_branch_name, get_receipt_handle, get_commit_id
    except Exception as e:
        print(f"Error while extracting branch name: {e}")
        return None

# Function to parse the datetime string and return a datetime object
def parse_datetime(datetime_str):
    #print(datetime.strptime(datetime_str, "datetime.datetime(%Y, %m, %d, %H, %M, %S, tzinfo=tzlocal())"))
    datetime_str = str(datetime_str)
    
    return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S%z')


def lambda_handler(event, context):
    print(event)
    codepipeline_name = event["detail"]["pipeline"]
    account = event["account"]
    region = event["region"]
    print("Code Pipeline Name: ", codepipeline_name)
    # ----Get details from Pipeline state-----
    """
    response_pipe = codepipeline.get_pipeline_state(name=codepipeline_name)
    print('---current pipeline state---')
    print(response_pipe)
    pipeline_name_from_response = response_pipe["pipelineName"]
    # Get pipeline status and pipeline execution id from response
    pipeline_executionId = response_pipe["stageStates"][0]["latestExecution"]["pipelineExecutionId"]  
    pipeline_status = response_pipe["stageStates"][-1]["latestExecution"]["status"]
    """
    # get pipeline name, pipeline execution id and status
    pipeline_executionId = event["detail"]["execution-id"]
    pipeline_status = event["detail"]["state"]
    print("Pipeline Execution ID: ", pipeline_executionId)
    print("Pipeline Execution Status: ", pipeline_status)

    # ----Get details from Pipeline execution-----
    execution_response = codepipeline.get_pipeline_execution(
        pipelineName=codepipeline_name,
        pipelineExecutionId=pipeline_executionId,
    )
    print("--execution response--")
    print(execution_response)
    filtered_artifacts = [
        artifact
        for artifact in execution_response["pipelineExecution"]["artifactRevisions"]
        if artifact["name"] == "SourceArtifact"  # check
    ]
    # Print the filtered artifacts
    for artifact in filtered_artifacts:
        print(artifact)
        print("Name:", artifact["revisionUrl"])
        print("Revision ID:", artifact["revisionId"])
    url = artifact["revisionUrl"]
    # latest_commit_id = artifact["revisionId"]
    pipeline_status = execution_response["pipelineExecution"]["status"]
    print(pipeline_status)
    parts = url.split("/")
    if len(parts) >= 5:  # Ensure that there are enough parts in the URL
        repository_name = parts[-3]
        print(
            f"The repository name associated with the latest pipeline execution is: {repository_name}"
        )
    else:
        print("URL format is unexpected. Unable to extract repository name.")
    print("Pipeline exection ID", pipeline_executionId)

    # ----Get branch & variant name-----
    print("--Get branch & variant name---")
    sqs_queue_url = extract_sqs_url(codepipeline_name)
    print("SQS Queue URL: " + sqs_queue_url)
    branch_name, receipt_handle, latest_commit_id = extract_from_sqs(sqs_queue_url)
    print("Latest Commit Id:-", latest_commit_id)
    # Delete the message from the queue
    sqs_client.delete_message(QueueUrl=sqs_queue_url, ReceiptHandle=receipt_handle)
    print(f"Branch Name : {branch_name}")
    # prefix_branch = branch_name.split("/")[1].upper()
    prefix_branch = extract_variant(branch_name)
    print(f"VARINT: {prefix_branch}")
    branch_log_name = 'logs/'+re.sub(r'\W+', '_', branch_name)
    print(f"Branch Log Name : {branch_log_name}")

    # ----Get details from commit-----
    response = code_commit.get_commit(
        repositoryName=repository_name, commitId=latest_commit_id
    )
    print("--response from code commit--")
    print(response)
    # Access the 'commit' dictionary inside the 'response' dictionary
    commit_details = response["commit"]
    # Access the 'author' dictionary inside the 'commit' dictionary
    author_details = commit_details["author"]
    # Access the 'name' field inside the 'author' dictionary
    author_name = author_details["name"]
    author_email = author_details["email"]
    author_date = author_details["date"]
    epoch_seconds = int(author_date.split()[0])
    author_date_utc = datetime.utcfromtimestamp(epoch_seconds)
    committer_details = commit_details["committer"]
    Committer_name = committer_details["name"]
    committer_email = committer_details["email"]
    committer_Date = committer_details["date"]
    epoch_second_commit = int(committer_Date.split()[0])
    committer_Date_utc = datetime.utcfromtimestamp(epoch_second_commit)
    commit_id = commit_details["commitId"]
    tree_id = commit_details["treeId"]
    parents = commit_details["parents"]
    #recipients = author_email
    recipients = committer_email
    utc_offset = timedelta(hours=5, minutes=30)
    # Get current UTC time
    utc_now = datetime.now(timezone.utc)

    # Apply the UTC offset
    local_time = utc_now + utc_offset

    # S3 BUCKET
    print(f"S3 BUCKET NAME : {BUCKET_NAME}")
    prefixes = ["DCU-Digital-Twin/", "DCU/", "DTDJ/", "marelli/"]
    PROJECT = "DTDJ"
    SUB_PROJECT = codepipeline_name[:3]
    print(f"Project Name : {PROJECT}")
    print(f"Sub Module Name : {SUB_PROJECT}")
    latest_object = None
    latest_object_key = None
    for prefix in prefixes:
        if prefix == "DTDJ/":
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{prefix}SOC/")
            # print(json.dumps(response))
            print(response)
            all_objects = []
            unique_objects = set()
            # ---------check condition for Success--------------
            if pipeline_status == "Succeeded":
                matching_objects = [
                    obj
                    for obj in response.get("Contents", [])
                    if prefix_branch in obj["Key"]
                    and "logs" in obj["Key"]
                    and obj["LastModified"] <= local_time
                ]

                ''' 
                latest_object_key = latest_object["Key"]
                dates = latest_object_key.split("/")[3]
                prefix_e = latest_object_key.split("/")[4]
                '''
                print("--matching objects--")
                print(matching_objects)
                latest_object = max(matching_objects, key=lambda x: x["LastModified"])
                print("Latest_object in suceeded", latest_object["Key"])
                latest_object_key = latest_object["Key"]
                dates = latest_object_key.split("/")[3]
                prefix_e = latest_object_key.split("/")[4]

                hyperlinks = [""]
                presigned_url = generate_presigned_url(BUCKET_NAME, latest_object["Key"])
                logfile = latest_object_key.split("/")[6]
                hyperlinks = [f'<a href="{presigned_url}">{logfile}</a>'] 
                ''' 
                for index, obj in enumerate(matching_objects):
                    if index < 1:
                        presigned_url = generate_presigned_url(BUCKET_NAME, obj["Key"])
                        print('--obj--')
                        print(obj)
                        logfile = obj["Key"].split("/")[6]
                        hyperlinks[index] = f'<a href="{presigned_url}">{logfile}</a>'
                '''

                print("Dates", dates)
                print("Prefix", prefix_e)
                print(f"{prefix}SOC/{prefix_branch}/{dates}/{prefix_e}/")

                try:
                    response_pipelinestatus = s3.list_objects_v2(
                        Bucket=BUCKET_NAME,
                        Prefix=f"{prefix}SOC/{prefix_branch}/{dates}/{prefix_e}/logs/",
                    )
                    if "Contents" in response_pipelinestatus:

                        for obj in response_pipelinestatus["Contents"]:

                            if (
                                latest_object is None
                                or obj["LastModified"] > latest_object["LastModified"]
                            ):
                                latest_object = obj
                            response_variant = s3.list_objects_v2(
                                Bucket=BUCKET_NAME,
                                Prefix=f"{prefix}SOC/{prefix_branch}/{dates}/{prefix_e}/",
                            )
                            # -------extract content from text file-----------
                            if "Contents" in response_variant:
                                for obj in response_variant["Contents"]:
                                    if obj["Key"].endswith(".txt"):
                                        try:
                                            version_object = s3.get_object(
                                                Bucket=BUCKET_NAME, Key=obj["Key"]
                                            )
                                        except Exception as e:
                                            print(f"Error retrieving object: {e}")
                                        with version_object["Body"] as file:
                                            file_content_bytes = file.read()
                                            file_content = file_content_bytes.decode(
                                                "utf-8"
                                            )

                                            # Extract SOC_VERSION and SOC_JFROGPATH
                                            soc_version_line = next(
                                                (
                                                    line
                                                    for line in file_content.split("\n")
                                                    if "SOC_VERSION" in line
                                                ),
                                                None,
                                            )
                                            if soc_version_line:
                                                _, SOC_Version = map(
                                                    str.strip,
                                                    soc_version_line.split(":", 1),
                                                )
                                                print("SOC VERSION:", SOC_Version)
                                            else:
                                                print("SOC_VERSION not found in file.")

                                            jfrogpath_line = next(
                                                (
                                                    line
                                                    for line in file_content.split("\n")
                                                    if "SOC_JFROGPATH" in line
                                                ),
                                                None,
                                            )
                                            if jfrogpath_line:
                                                _, SOC_Artifactory = map(
                                                    str.strip,
                                                    jfrogpath_line.split(":", 1),
                                                )
                                                print("SOC_JFROGPATH:", SOC_Artifactory)
                                            else:
                                                print(
                                                    "SOC_JFROGPATH not found in file."
                                                )

                            else:
                                print("No objects found.")
                except Exception as e:
                    print(f"Error: {e}")
            # ---------check condition for Failed--------------
            elif pipeline_status == "Failed":
                print('--inside failed--')
                print(local_time)
                matching_objects = [
                    obj
                    for obj in response.get("Contents", [])
                    if prefix_branch in obj["Key"]
                    and "logs" in obj["Key"]
                    #and obj["LastModified"] <= local_time
                ]
                print(matching_objects)
                '''  
                latest_object = max(matching_objects, key=lambda x: x["LastModified"])
                print("Latest_object", latest_object["Key"])
                latest_object_key = latest_object["Key"]
                ''' 
                sorted_objects = sorted(matching_objects, key=lambda x: (branch_log_name in x["Key"], parse_datetime(x["LastModified"])), reverse=True)
                latest_object = sorted_objects[0]
                latest_object_key = latest_object["Key"]
                print(latest_object)
                logfile = latest_object_key.split("/")[6]
                print(logfile)

                hyperlinks = [""]
                presigned_url = generate_presigned_url(BUCKET_NAME, latest_object["Key"])
                
                print(presigned_url)
                #logfile = latest_object_key.split("/")[6]
                #print(logfile)
                hyperlinks = [f'<a href="{presigned_url}">{logfile}</a>'] 
                '''
                for index, obj in enumerate(matching_objects):
                    if index < 2:
                        presigned_url = generate_presigned_url(BUCKET_NAME, obj["Key"])
                        logfile = obj["Key"].split("/")[6]
                        hyperlinks[index] = f'<a href="{presigned_url}">{logfile}</a>'
                
                for index, obj in enumerate(latest_object):
                    if index < 1:
                        presigned_url = generate_presigned_url(BUCKET_NAME, latest_object[obj])
                        logfile = latest_object[obj]
                        logfile = logfile.split('/')[6]
                        print(logfile)
                        hyperlinks[index] = f'<a href="{presigned_url}">{logfile}</a>'
                '''

                dates = latest_object_key.split("/")[3]
                prefix_e = latest_object_key.split("/")[4]
                response_pipelinestatus_failed = s3.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    Prefix=f"{prefix}SOC/{prefix_branch}/{dates}/{prefix_e}/logs/",
                )
                if "Contents" in response_pipelinestatus_failed:
                    for obj in response_pipelinestatus_failed["Contents"]:
                        if (
                            latest_object is None
                            or obj["LastModified"] > latest_object["LastModified"]
                        ):
                            latest_object = obj
                        print(latest_object)
            attachments = []

    subject = f"Pipeline Build Status Notification {PROJECT} {SUB_PROJECT} {branch_name} {pipeline_status}"
    access_token = obtain_access_token(tenant_id, client_id, client_secret)
    if access_token:
        # --------create body for Success--------------
        if pipeline_status == "Succeeded":
            # If the build status is success, set the color to green and send email without attachments
            build_status_color = "#008000"  # Green color
            # No attachment message for success
            attachment_message = "S3 path logs link will get expired in 5 days.Please download before it expires."
            build_status_html = f'<td style="width: 60.5228%; background-color: #ffffff; height: 45px;"><strong><span style="color: {build_status_color};">{pipeline_status}</span></strong></td>'
            body = f"""<h2><span style="color: #136dbf;"></span>DTDJ Pipeline Build Status report was triggered</h2>
                <table style="height: 245px; width: 70%; border-collapse: collapse;" border="1" cellspacing="70" cellpadding="5">
                    <tbody style="font-family: Arial, sans-serif; font-size: 12px;">
                        <tr style="height: 45px;">
                            <td style="width: 22.6262%; background-color: #f2f3f3; height: 45px;">
                                <span style="color: #16191f;"><strong>Build Status</strong></span>
                            </td>
                            {build_status_html}
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Account</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">
                                <p>{account} {region}</p>
                            </td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Commit Id</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{latest_commit_id}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Repository Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{repository_name}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Branch Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{branch_name}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Author Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{author_name}</td>    
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Author Email</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {author_email}</td>       
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Author Commited Date</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {author_date_utc}</td>     
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Committer Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {Committer_name}</td>       
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Committer Email</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {committer_email}</td>     
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Commited Date</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {committer_Date_utc}</td>         
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>SOC Version</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{SOC_Version}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>SOC Jfrog Path</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"></strong>{SOC_Artifactory}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>SOC S3 Path</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"></strong>{hyperlinks[0]}</td>
                        </tr>
                    </tbody>
                </table>
                <span style="font-family: Arial, sans-serif; font-size: 13px; color: blue; font-style: italic;">&#9432; <b>Notice:</b>{attachment_message}</span>
                <p style="color: red; font-style: italic;">Kindly note that this is a system-generated unattended mailbox; hence, please do not reply back to this mail.</p>
            """
        # --------create body for Fail--------------
        if pipeline_status == "Failed":
            # If the build status is failed, set the color to red and send email with attachments
            build_status_color = "#d13212"  # Red color
            attachment_message = "S3 path logs link will get expired in 5 days.Please download before it expires."
            build_status_html = f'<td style="width: 60.5228%; background-color: #ffffff; height: 45px;"><strong><span style="color: {build_status_color};">{pipeline_status}</span></strong></td>'
            body = f"""<h2><span style="color: #136dbf;"></span>DTDJ Pipeline Logs was triggered</h2>
                 <table style="height: 245px; width: 70%; border-collapse: collapse;" border="1" cellspacing="70" cellpadding="5">
                    <tbody style="font-family: Arial, sans-serif; font-size: 12px;">
                        <tr style="height: 45px;">
                            <td style="width: 22.6262%; background-color: #f2f3f3; height: 45px;">
                                <span style="color: #16191f;"><strong>Build Status</strong></span>
                            </td>
                            {build_status_html}
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Account</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">
                                <p>{account} {region}</p>
                            </td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Commit Id</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{latest_commit_id}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Repository Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{repository_name}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Branch Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{branch_name}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Author Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{author_name}</td>       
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Author Email</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{author_email}</td>            
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Author Commited Date</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {author_date_utc}</td>       
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Committer Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {Committer_name}</td>        
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Committer Email</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {committer_email}</td>          
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Commited Date</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {committer_Date_utc}</td>        
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>SOC S3 Path</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {hyperlinks[0]}</td>        
                        </tr>
                        <!-- ... Other table rows ... -->
                    </tbody>
                 </table>
                <span style="font-family: Arial, sans-serif; font-size: 13px; color: blue; font-style: italic;">&#9432; <b>Notice:</b>{attachment_message}</span>
                <p style="color: red; font-style: italic;">Kindly note that this is a system-generated unattended mailbox; hence, please do not reply back to this mail.</p>
            """
            print("send mail for fail")
        # --------create body for Stop--------------
        if pipeline_status == "Stopped":
            # If the build status is success, set the color to green and send email without attachments
            build_status_color = "#808080"  # Grey color
            # No attachment message for success
            attachment_message = "S3 path logs link will get expired in 5 days.Please download before it expires."
            build_status_html = f'<td style="width: 60.5228%; background-color: #ffffff; height: 45px;"><strong><span style="color: {build_status_color};">{pipeline_status}</span></strong></td>'
            body = f"""<h2><span style="color: #136dbf;"></span>DTDJ Pipeline Logs was triggered</h2>
                 <table style="height: 245px; width: 70%; border-collapse: collapse;" border="1" cellspacing="70" cellpadding="5">
                    <tbody style="font-family: Arial, sans-serif; font-size: 12px;">
                        <tr style="height: 45px;">
                            <td style="width: 22.6262%; background-color: #f2f3f3; height: 45px;">
                                <span style="color: #16191f;"><strong>Build Status</strong></span>
                            </td>
                            {build_status_html}
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Account</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">
                                <p>{account} {region}</p>
                            </td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Commit Id</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{latest_commit_id}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Repository Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{repository_name}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; height: 45px; background-color: #f2f3f3;\"><span style=\"color:
                                    #16191f;\"><strong>Branch Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{branch_name}</td>
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Author Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{author_name}</td>       
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Author Email</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\">{author_email}</td>            
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Author Commited Date</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {author_date_utc}</td>       
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Committer Name</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {Committer_name}</td>        
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Committer Email</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {committer_email}</td>          
                        </tr>
                        <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>Commited Date</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {committer_Date_utc}</td>        
                        </tr>
                         <tr style=\"height: 45px;\">
                            <td style=\"width: 22.6262%; background-color: #f2f3f3; height: 45px;\"><span style=\"color:
                                    #16191f;\"><strong>SOC S3 Path</strong></span></td>
                            <td style=\"width: 60.5228%; height: 45px;\"> {hyperlinks[0]}</td>        
                        </tr>
                        <!-- ... Other table rows ... -->
                    </tbody>
                </table>
                <span style="font-family: Arial, sans-serif; font-size: 13px; color: blue; font-style: italic;">&#9432; <b>Notice:</b>{attachment_message}</span>
                <p style="color: red; font-style: italic;">Kindly note that this is a system-generated unattended mailbox; hence, please do not reply back to this mail.</p>
            """
        send_email(
            access_token,
            sender,
            recipients,
            cc_recipients,
            subject,
            body,
            attachments,
        )
        print("Email Sent Successfully !!")
    else:
        print("Error obtaining access token")
