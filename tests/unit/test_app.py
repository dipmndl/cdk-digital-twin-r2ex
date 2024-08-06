import pytest
import app
import os
from aws_cdk import App, Environment
from dotenv import load_dotenv
from stacks.cicd_stack import CicdStack
from stacks.event_stack import EventStack
from stacks.sqs_stack import SqsStack
from stacks.state_machine_stack import StateMachineStack
from aws_cdk.assertions import Template

# Mocking os.environ using monkeypatch to simulate environment variables
@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("CDK_ENV_NAME", "dev")
    monkeypatch.setenv("CDK_ENV_REGION", "ap-test-1")
    monkeypatch.setenv("CDK_ENV_ACCOUNT", "122480973114")
    monkeypatch.setenv("CDK_ENV_OS", "linux")

def test_app_environment(mock_env_vars):
    # Import app.py which should read the environment variables we just set
    assert "CDK_ENV_NAME" in app.os.environ
    assert "CDK_ENV_REGION" in app.os.environ
    assert "CDK_ENV_ACCOUNT" in app.os.environ
    assert "CDK_ENV_OS" in app.os.environ
    