import pytest
import aws_cdk as core
import aws_cdk.assertions as assertions
from stacks.sqs_stack import SqsStack
import unittest.mock

# Mock environment variables that the stack expects
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv('VPC_ID', 'vpc-0ce08f60eba542855')
    monkeypatch.setenv('PRIVATE_SUBNETS_IDS', 'subnet-0cac1c0fa6aec3b5a,subnet-02a6f16ebd006cb9d')
    monkeypatch.setenv('CDK_ENV_REGION', 'ap-south-1')
    monkeypatch.setenv('SQS_TIMEOUT', '30')
    monkeypatch.setenv('SQS_RETENSION', '72')
    monkeypatch.setenv('SQS_MAX_SIZE', '262144')
    monkeypatch.setenv('SQS_VARIANTS', 'r2ex')

@pytest.fixture()
def sqs_stack():
    app = core.App()
    with unittest.mock.patch('aws_cdk.aws_ec2.Vpc.from_lookup', return_value=unittest.mock.MagicMock(id='VpcId')):
        stack = SqsStack(app, "SqsStack-testing", env={
            'region': 'ap-south-1',
            'account': '932780615243'
        })
    template =  assertions.Template.from_stack(stack)
    return template


def test_queue_creation(sqs_stack):
    # SQS_VARIANTS will create one queues named r2exfrom the fixture
    sqs_stack.has_resource_properties("AWS::SQS::Queue", {
        "FifoQueue": True,
        "ContentBasedDeduplication": True,
        "VisibilityTimeout": 30,  # from SQS_TIMEOUT env var
        "MessageRetentionPeriod": 3600,  # calculated from 1 hour in SQS_RETENSION
        "MaximumMessageSize": 1024,  # from SQS_MAX_SIZE env var
        "QueueName": "SQS-QUEUE-R2EX.fifo"  # expects variant1 to be upper-cased and suffixed with .fifo
    })


def test_sqs_queue_exists(sqs_stack):
    # Check for the existence of an SQS queue resource in the stack
    sqs_resources = sqs_stack.find_resources("AWS::SQS::Queue")

    # Assert that there is only one SQS queue defined in the stack
    assert len(sqs_resources) == 1, "No SQS queue found in the stack."
'''     
def test_outputs(sqs_stack):
    output_name = "SQS_Queue_URL_digital-twin_r2ex"
    export_name = "sqsurls"  # Replace with the actual export name, if it is needed for the test
    
    # Using find_outputs to verify the output exists
    outputs = sqs_stack.find_outputs(output_name)
    assert len(outputs) > 0, f"Output {output_name} not found in the template!"
    
    # If specific properties are also to be tested, use has_output
    sqs_stack.has_output(output_name, {
        "Export": {
            "Name": export_name
        }
    })
'''