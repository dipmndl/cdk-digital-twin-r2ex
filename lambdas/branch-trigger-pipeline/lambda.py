import json
import boto3
import os
# Load necessary AWS SDK clients
codepipeline_client = boto3.client('codepipeline')
sqs_client = boto3.client('sqs')
# Declare variables
branch_name,variant_name,variant_type,message_group_id,message_deduplication_id,pipeline_name = "","","","","",""
# env variables
  # Identify which branch pipeline should trigger(prefer 'release')
BRANCH_KEY = os.environ["BRANCH_KEY"]

  # URL of your SQS queue
SQS_QUEUE_URL_R2EX = os.environ["SQS_QUEUE_URL_R2EX"] 
PIPELINE_NAME = os.environ["PIPELINE_NAME"]

def lambda_handler(event, context):
    # TODO implement
    # Log the received event
    #print("Received event: " + json.dumps(event))
    print(event)
    repo_name = event["detail"]["repositoryName"]
    branch_type = event["detail"]["referenceType"]
    branch_name = event["detail"]["referenceName"]
    event_type = event["detail"]["event"]
    commit_id = event["detail"]["commitId"]
    pipeline_name = extract_pipeline_name(repo_name)
    print("Pipeline Name: "+pipeline_name)
    response = codepipeline_client.get_pipeline(
        name= pipeline_name
    )
    print("Event Type: "+event_type)
    print("Repo Name: "+repo_name)
    print("Event Occurs In: "+branch_type)
    print("Branch Name: "+branch_name)
    # get variant name and variant type
    variant_name,sqs_queue_url = extract_variant_sqs(repo_name)
    variant_type = extract_variant_type(branch_name)
    message_group_id,message_deduplication_id = check_branch_name(branch_name, variant_type, variant_name)
    print("Variant Name: "+variant_name)  
    print("Variant Type: "+variant_type)
    print("Message Group Id: "+message_group_id)
    print("Message Deduplication Id: "+message_deduplication_id)
    print("SQS Queue URL: "+sqs_queue_url)
    #pipeline details 
    print('Pipeline Details')
    print(response)
    
    branch_repo_commitid = branch_name+','+repo_name+','+commit_id
    # Send message to SQS FIFO queue
    response = sqs_client.send_message(
        QueueUrl=sqs_queue_url,
        MessageGroupId=message_group_id,
        MessageDeduplicationId=message_deduplication_id,
        MessageBody=branch_repo_commitid
        )
    print("Message sent:", response['MessageId'])
    execution_response = codepipeline_client.start_pipeline_execution(
    name=pipeline_name
    )
    #print('Pipeline execution result')
    #print(execution_response)
    
# create function to extract variant name from repo name
def extract_variant_sqs(repo_name):
    try:
        # find which variant name is among '3e5','12' or '7' available inside repo name      
        if repo_name.find("la") != -1:
            res = "la"
            sqs_res = SQS_QUEUE_URL_R2EX
        elif repo_name.find("manifest") != -1:
            res = "manifest"
            sqs_res = SQS_QUEUE_URL_R2EX
        else:
            print("Variant Name Not Found")
            res = ""
        return res,sqs_res
    except Exception as e:
        print(e)
        return None
# create function to extract variant type from branch name
def extract_variant_type(branch_name):
    try:
        # find which variant type is among 'dt' or 'dj' available inside branch name
        if branch_name.find("DigitalTwin") != -1:
            res = "digitaltwin"
        elif branch_name.find("mm_release") != -1:
            res = "mm"
        else:
            print("Variant Type Not Found")
            res = ""
        return res
    except Exception as e:
        print(e)
        return None
# create function to check 'dt' or 'dj' and branch key is available inside branch name
def check_branch_name(branch_name, variant_type, variant_name):
    try:
        # check branch_name first word before first '/'
        branch_name_first_word = branch_name.split('/')[0]
        # check 'dt' or 'dj' and release branch are available inside branch name
        if branch_name.find("DigitalTwin") != -1 and branch_name_first_word in BRANCH_KEY:
            print("Branch Name Contains 'DigitalTwin' and "+branch_name_first_word+" branch")
            generate_message_group_id = branch_name
            generate_message_deduplication_id = variant_name+'/'+branch_name_first_word+'/'+variant_type   
        elif branch_name.find("mm_release") != -1 and branch_name_first_word in BRANCH_KEY:
            print("Branch Name Contains 'mm_release' and "+branch_name_first_word+" branch")
            generate_message_group_id = branch_name
            generate_message_deduplication_id = variant_name+'/'+branch_name_first_word+'/'+variant_type  
        else:
            branch_key_string = ','.join(BRANCH_KEY)
            print("Branch Name Does Not Contain 'DigitalTwin' or 'mm_release' and any of the "+branch_key_string+" branch")
            generate_message_group_id = ""
            generate_message_deduplication_id = ""

        return generate_message_group_id, generate_message_deduplication_id
    except Exception as e:
        print(e)
        return None

# create function to extract pipeline name from repo name
def extract_pipeline_name(repo_name):
    try:
        # find which variant name is among '3e5','12' or '7' available inside repo name      
        if repo_name.find("la") != -1:
            pipeline_name= PIPELINE_NAME
        elif repo_name.find("mm_release") != -1:
            pipeline_name=PIPELINE_NAME
        else:
            print("Pipeline Name Not Found")
            pipeline_name = ""
        return pipeline_name
    except Exception as e:
        print(e)
        return None    
    