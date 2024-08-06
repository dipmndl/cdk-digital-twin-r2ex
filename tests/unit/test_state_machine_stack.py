import json
import pytest
import aws_cdk as core
import aws_cdk.assertions as assertions
from stacks.state_machine_stack import StateMachineStack


# Create a fixture for the stack
@pytest.fixture
def test_state_machine_stack():
    app = core.App()
    stack = StateMachineStack(app, "StateMachineStack-testing")
    template =  assertions.Template.from_stack(stack)
    return template


def test_state_machine_exists(test_state_machine_stack):
    # Check for the existence of a State Machine resource in the stack
    resources = test_state_machine_stack.find_resources('AWS::StepFunctions::StateMachine')
    assert len(resources) > 0, "No State Machine found in the stack."

def test_state_machine_has_execution_role(test_state_machine_stack):
    # Assuming only one state machine in your stack for simplification
    state_machine = next(iter(test_state_machine_stack.find_resources('AWS::StepFunctions::StateMachine').values()))

    # Check that the State Machine has an execution role attached
    assert 'RoleArn' in state_machine['Properties'], "State Machine does not have an execution role assigned."

def test_ssm_document_exists(test_state_machine_stack):
    # Check for the existence of an SSM Document resource in the stack
    resources = test_state_machine_stack.find_resources('AWS::SSM::Document')

    assert len(resources) > 0, "No SSM Document found in the stack."

def test_ssm_document_output_exists(test_state_machine_stack):
    # Check for the existence of the SSM Document's output
    outputs = test_state_machine_stack.find_outputs('ssmname')

    # Assert that the output for the SSM Document name exists
    assert len(outputs) == 1, "Output for SSM Document name not found."

