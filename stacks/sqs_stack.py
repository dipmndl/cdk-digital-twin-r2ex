from aws_cdk import (
    Aws,
    Duration,
    aws_ec2 as ec2,
    aws_sqs as sqs,
    Stack,
    aws_iam as iam,
    aws_logs as logs,
    RemovalPolicy,
    aws_events as events,
    aws_events_targets as events_targets,
    CfnOutput,
)
from constructs import Construct
from dotenv import load_dotenv
import os
import json
from library.utility import Utility


load_dotenv()

EC2_STACK_CONFIG_FILE = "./config/ec2-config.json"
VPC_ID = os.environ["VPC_ID"]
PRIVATE_SUBNETS_IDS = (
    os.environ["PRIVATE_SUBNETS_IDS"].strip().split(",")
    if len(os.environ["PRIVATE_SUBNETS_IDS"]) > 0
    else None
)
REGION = os.environ["CDK_ENV_REGION"]
SQS_TIMEOUT = int(os.environ["SQS_TIMEOUT"])
SQS_RETENSION = int(os.environ["SQS_RETENSION"])
SQS_MAX_SIZE = int(os.environ["SQS_MAX_SIZE"])
SQS_VARIANTS = (
    os.environ["SQS_VARIANTS"].strip().split(",")
    if len(os.environ["SQS_VARIANTS"]) > 0
    else None
)


class SqsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_lookup(self, "vpc", vpc_id=VPC_ID)
        if not vpc:
            print("Failed finding VPC {}".format(VPC_ID))
            return

        with open(EC2_STACK_CONFIG_FILE, "r") as f:
            ec2s = json.loads(f.read())

        for e in ec2s:
            name = e["name"]

        # Create a property to store queue URLs
        self.queue_urls = []    
        # create a fifo sqs queue from list of sqs variants
        for i in SQS_VARIANTS:
            queue = sqs.Queue(
                self,
                "SQS_Queue_" + name + "_" + i,
                queue_name="SQS-QUEUE-" + i.upper() + ".fifo",
                fifo=True,
                fifo_throughput_limit=sqs.FifoThroughputLimit.PER_MESSAGE_GROUP_ID,
                deduplication_scope=sqs.DeduplicationScope.MESSAGE_GROUP,
                content_based_deduplication=True,
                visibility_timeout=Duration.seconds(SQS_TIMEOUT),
                retention_period=Duration.hours(SQS_RETENSION),
                removal_policy=RemovalPolicy.DESTROY,
                max_message_size_bytes=SQS_MAX_SIZE,
                encryption=sqs.QueueEncryption.SQS_MANAGED,
            )
            # Store the queue URL for passing to another stack
            self.queue_urls.append(queue.queue_url)
            
        # Output the Queue URL to the CloudFormation template
        CfnOutput(self, "SQS_Queue_URL_" + name + "_" + i, value=str(self.queue_urls), export_name="sqsurls")
        self.sqsurls = self.queue_urls
