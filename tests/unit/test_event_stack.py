import aws_cdk as core
import aws_cdk.assertions as assertions
import pytest
from stacks.event_stack import EventStack

@pytest.fixture(scope="session")
def simple_template():
    app = core.App()
    
    # Mock values for the additional constructor parameters
    mock_statemachine_arn = "arn:aws:states:REGION:ACCOUNT_ID:stateMachine:StateMachineName"
    mock_ssmDocumentname = "SSMDocumentName"
    mock_sqs_urls = ["https://sqs.REGION.amazonaws.com/ACCOUNT_ID/QueueName"]

    stack = EventStack(app, "eventstack-testing", 
                       statemachine_arn=mock_statemachine_arn,
                       ssmDocumentname=mock_ssmDocumentname,
                       sqs_urls=mock_sqs_urls)

    template =  assertions.Template.from_stack(stack)
    return template
# example tests. To run these tests, uncomment this file along with the example
# Check lambda run time version
def test_lambda_props(simple_template):

    simple_template.has_resource_properties("AWS::Lambda::Function", {
        "Runtime": "python3.11"  
    }
    )
# check lambda handler   
def test_lambda_handler(simple_template):
        simple_template.has_resource_properties("AWS::Lambda::Function", {
            "Handler": "lambda.lambda_handler" 
        }
        )
# check no of lambda function
def test_lambda_count(simple_template):
        simple_template.resource_count_is("AWS::Lambda::Function", 6) 

   
# test case to check whether iam policy allow for all resources
def test_iam_policy_allow_all(simple_template):
    policy_statements = simple_template.find_resources("AWS::IAM::Policy")
    for logical_id, policy_statement in policy_statements.items():
        # Go through each Statement in the Policy
        for statement in policy_statement['Properties']['PolicyDocument']['Statement']:
            assert statement['Effect'] == 'Allow', \
                f"Statement with logical ID {logical_id} does not have 'Allow' effect."

            # Check if there's any statement that allows "*" on all resources
            if statement.get('Resource') == "*":
                assert statement.get('Action') != '*'

            # If you want to explicitly confirm that no policies allow all actions on specific or all resources,
            # uncomment the following line:
            # assert statement.get('Action') != '*' or statement.get('Resource') != '*', \
            #     f"Statement with logical ID {logical_id} should not allow all ('*') actions on all resources.
      
            
 # test case to check whether iam policy allow admin access or not
def test_iam_policy_admin(simple_template):
      policy_statements = simple_template.find_resources("AWS::IAM::Policy")
      for logical_id, policy_statement in policy_statements.items():
        # Go through each Statement in the Policy
        for statement in policy_statement['Properties']['PolicyDocument']['Statement']:
            # Check if there's any statement that allows "admin:*" on all resources.
            assert statement.get('Action') != 'admin:*'
            assert statement.get('Resource') != 'admin:*'  
        
  # test case to check lambda is created any s3 bucket or not
def test_lambda_trigger_s3(simple_template):
      lambda_functions = simple_template.find_resources("AWS::Lambda::Function")
      for logical_id, lambda_function in lambda_functions.items():
        # Go through each Statement in the Policy
        for statement in lambda_function['Properties']:
            if statement == 'Events':
                assert lambda_function['Properties']['Events']['s3:ObjectCreated:*']['Type'] == 'S3'
                assert lambda_function['Properties']['Events']['s3:ObjectCreated:*']['Properties']['Bucket'] == 'autopilot-testing-bucket'
            else:
                continue


         

            
                 


