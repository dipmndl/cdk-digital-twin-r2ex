#!/bin/bash

cdk_synth() {
    # Run `cdk synth` command
    cdk synth
}

run_pytest() {
    # Run pytest command for unit test case execution on the test folder and output results in JUnit XML and HTML format
    pytest --cov=tests --junitxml=test-results.xml --cov-branch --cov-report xml:coverage.xml --cov-report html:coverage_html

}

# Step 1: Synthesize CloudFormation templates
cdk_synth

# Step 2: Run pytest command
run_pytest


