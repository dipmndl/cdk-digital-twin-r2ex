import os
import aws_cdk as core
import aws_cdk.assertions as assertions
import pytest
from stacks.cicd_stack import CicdStack
from unittest.mock import patch, MagicMock

# Create a fixture for the stack
@pytest.fixture
def cicd_stack():
    app = core.App()
    stack = CicdStack(app, "cicdstack-testing", ssmDocumentname="test-ssm-document", env={
        'region': 'ap-south-1',
        'account': '932780615243',
    })
    template =  assertions.Template.from_stack(stack)
    return template
# example tests. To run these tests, uncomment this file along with the example


# Test the CodeCommit repository creation
def test_codecommit_repository(cicd_stack):
    cicd_stack.resource_count_is("AWS::CodeCommit::Repository", 1)

# Test the CodePipeline role creation
def test_codepipeline_role(cicd_stack):
    cicd_stack.has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "codepipeline.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
        }
    )

# Test for the existence of the custom action registration
def test_custom_action_registration(cicd_stack):
    cicd_stack.has_resource('AWS::CodePipeline::CustomActionType', {})

# Test any environment variables are properly loaded
@patch.dict('os.environ', {
    'VPC_ID': 'vpc-0ce08f60eba542855',
    'PRIVATE_SUBNETS_IDS': 'subnet-0cac1c0fa6aec3b5a, subnet-02a6f16ebd006cb9d',
    'SOURCE_REPO': 'digital-twin-r2ex-demo',
    'SOURCE_BRANCH': 'main',
    'PIPELINE_TIMEOUT': '180',
    'CDK_ENV_REGION': 'ap-south-1',
    'CUSTOM_ACTIONS_PROVIDER_NAME': 'EC2-CodePipeline-Builder-R2EX',
    'CUSTOM_ACTIONS_PROVIDER_VERSION': '1'
})
def test_environment_variables():
    # Mocking load_dotenv and AWS context retrievals
    with patch('dotenv.load_dotenv', MagicMock()), \
         patch('aws_cdk.aws_ec2.Vpc.from_lookup') as mock_vpc_lookup:
        # Mock the Vpc.from_lookup method to return a simple Vpc object
        mock_vpc_lookup.return_value = MagicMock(name="MockVpc")

        # Create the app and stack with mocked 'env' to simulate AWS environment
        app = core.App()
        CicdStack(app, "CicdStack", ssmDocumentname="test-ssm-document", env={
            'region': 'ap-south-1',
            'account': '932780615243',
        })
        # Now you can add assertions or further tests if necessary


         

            
                 


