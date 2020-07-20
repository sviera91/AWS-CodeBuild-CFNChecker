# CloudFormation Checker

This python script can be used in CodeBuild as part of the deployment process for Cloudformation stacks using CodePipeline.
This script is capable of retrieving the file paths of each stack being deployed and perform cfn-lint, cfn_nag and aws cfn
validation tasks against each stack. This can provide a level of security check to ensure all stacks follow correct syntax and best 
practices before deployment.

## Requirements

Ensure that the following items are taken care of first:

- Ensure CodeBuild IAM role has access to CodePipeline and CloudFormation actions
- Create appropriate buildspec file (example available [here](buildspec.yml))
    - Ensure the CodeBuild container deploys both Python and Ruby runtimes
    - Install cfn-lint as part of the CodeBuild container creation
    - Install cfn_nag as part of the CodeBuild container creation
