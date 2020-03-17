import argparse
import boto3
import logging
import json
import cfnlint.core
import subprocess
import shlex
import sys
import traceback

from botocore.config import Config

config = Config(
    retries=dict(
        max_attempts=10
    )
)

logger = logging.getLogger(__name__)
shared_services_session = boto3.session.Session()


# Retrieve stacks to be checked
def fetch_pipeline_definition(pipeline_name, region):
    """This function creates an array with all the file paths
    for any CloudFormation stack being deployed in a given pipeline.
    It also converts any packaged.yaml file into template.yaml for stacks
    packaged using SAM.

    Arguments:
        pipeline_name {[string]} -- Name of the pipeline where the build takes place
        region {[string]} -- Region code where the pipeline resides e.g. us-west-2

    Returns:
        templates {[array]} -- Array with the file path of every cfn stack to be checked
    """
    try:
        cp_client = boto3.client('codepipeline', region_name=region)
        pipeline_definition = cp_client.get_pipeline(
            name=pipeline_name
        )
    except cp_client.exceptions.PipelineNotFoundException:
        print(f"Pipeline {pipeline_name} does not exist in region {region}")

    templates = []

    for stage in pipeline_definition["pipeline"]["stages"]:
        for action in stage["actions"]:
            if "TemplatePath" in action["configuration"]:
                templates.append(
                    action["configuration"]["TemplatePath"].split("::")[1]
                )

    for template in templates:
        if "packaged" in template:
            fixed_name = template.replace("packaged", "template")
            templates.remove(template)
            templates.append(fixed_name)
    return templates


# cfn-lint process
def cfn_lint_checker(templates, region):
    """This function runs cfn-lint against the array of templates

    Arguments:
        templates {[array]} -- Array with the file path of every cfn stack to be checked
        region {[string]} -- Region code where the pipeline resides e.g. us-west-2
    """
    try:
        for template in templates:
            template_check = cfnlint.decode.cfn_yaml.load(template)
            cfnlint.core.configure_logging(None)
            rules = cfnlint.core.get_rules([], [], [])
            regions = [region]
            matches = cfnlint.core.run_checks(
                template,
                template_check,
                rules,
                regions)
            print(f'Errors & Warnings found for {template}:')
            print(matches)
    except Exception as e:
        print(f'There is an issue with template {template}. The error is: {e} \n')
        print('Traceback error logs are: \n')
        traceback.print_exc()


# CloudFormation Validation
def cfn_validator(templates):
    """This function runs cfn validate templates against the array of templates

    Arguments:
        templates {[array]} -- Array with the file path of every cfn stack to be checked
    """
    cfn_client = boto3.client('cloudformation', config=config)
    try:
        for template in templates:
            template_to_validate = open(template).read()
            print(f'Validating stack "{template}". If no output, stack is valid." \n')
            validation = cfn_client.validate_template(
                TemplateBody=template_to_validate
            )
    except Exception as e:
        print(f'There is an issue with template {template}. The error is: {e} \n')
        print('Traceback error logs are: \n')
        traceback.print_exc()


# cfn_nag
def cfn_nag_checker(templates):
    """This function runs cfn_nag against the array of templates

    Arguments:
        templates {[array]} -- Array with the file path of every cfn stack to be checked
    """
    try:
        for template in templates:
            run_command(f'cfn_nag_scan -i {template} -o txt', template)
    except Exception as e:
        print(f'There is an issue with template {template}. The error is: {e} \n')
        print('Traceback error logs are: \n')
        traceback.print_exc()

# Function to run shell commands
def run_command(command, template):
    """This function runs the shell command for cfn_nag since its built
    using ruby and not python

    Arguments:
        command {[string]} -- The cfn_nag to run e.g. cfn_nag_scan -i test.yaml -o txt
        template {[string]} -- Path for cfn template that comes from templates array
    """
    logger.debug("executing command: %s" % command)
    err = None
    output = None
    try:
        output = subprocess.check_output(shlex.split(
            command), stderr=subprocess.STDOUT).decode("utf-8")
        logger.debug(output)
    except subprocess.CalledProcessError as exc:
        logger.debug("Command failed with exit code %s, stderr: %s" %
                        (exc.returncode, exc.output.decode("utf-8")))
        err = exc.output.decode("utf-8")
    if err:
        if "Failures count: 0" not in err:
            logger.error(
                f'The template "{template}" has the following issues: \n{err}')
            print(
                f'There are failure issues with template "{template}". Look at the following output: \n{err}')
            sys.exit(1)
    else:
        print(
            f'There are no failures with template "{template}". Check for any warnings in output if present: {err} \n')


# launch all functions
def launch(pipeline_name, region):
    """Runs all the aforementioned functions

    Arguments:
        pipeline_name {[string]} -- Name of the pipeline where the build takes place
        region {[string]} -- Region code where the pipeline resides e.g. us-west-2
    """

    # Get stacks to be checked
    print('\nList of templates to check:')
    templates = fetch_pipeline_definition(pipeline_name, region)
    for template in templates:
        print(template)
    # cfn-lint checker
    print('\n---Running cfn-lint---')
    cfn_lint_checker(templates, region)
    # cfn validation
    print('\n---Running cfn validator---')
    cfn_validator(templates)
    # cfn_nag checker
    print('\n---Running cfn_nag---')
    cfn_nag_checker(templates)


# Set argument flags to be passed for script
if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument("-p", "--pipeline_name", help="Pipeline Name")
    PARSER.add_argument("-r", "--region", help="Target Region")

    ARGS, UNKNOWN = PARSER.parse_known_args()

    if ARGS.pipeline_name and ARGS.region:
        launch(ARGS.pipeline_name, ARGS.region)
