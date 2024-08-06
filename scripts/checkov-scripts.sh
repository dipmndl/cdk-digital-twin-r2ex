#!/bin/bash

cdk_synth() {
    # Run `cdk synth` command
    cdk synth
}

create_sca(){
    directory="sca"

    if [ ! -d "$directory" ]; then
        mkdir -p "$directory"
        echo "Directory created: $directory"
    else
        echo "Directory already exists: $directory"
    fi
}

move_stacks_to_sca() {
    # Get all synthesized CloudFormation templates and move them to the sca folder
    find cdk.out -name '*.template.json' -exec sh -c 'mv "$1" "sca/$(basename "$1" .template.json).yaml"' _ {} \;
}

run_checkov() {
    # Run Checkov code analysis on the sca folder and output results in JUnit XML format
    checkov -d sca --output junitxml --output-file checkov_report/

    # Run Checkov code analysis again without specifying output option to generate plain text file
    checkov -d sca --output-file checkov_report/
}

display_results() {
    # Display pass and fail results from the plain text file
    cat checkov_report/results_cli.txt
}

# Step 1: Synthesize CloudFormation templates
cdk_synth

# Step 2: Move stacks to sca folder
create_sca
move_stacks_to_sca

# Step 3: Run Checkov code analysis
run_checkov

# Step 4: Display pass and fail results
display_results
