#!/usr/bin/env python3
"""CDK app entry point.

To deploy:
  cd infra/
  pip install -r requirements.txt          # install CDK Python library
  npm install -g aws-cdk                   # install CDK CLI (requires Node.js)
  aws configure                            # set your AWS credentials
  cdk bootstrap                            # one-time setup per AWS account+region
  cdk deploy -c key_pair_name=YOUR_KEY     # deploy (omit key_pair_name to use SSM)
  cdk destroy                              # tear down all resources
"""

import aws_cdk as cdk
from football_league_stack import FootballLeagueStack

app = cdk.App()

FootballLeagueStack(
    app,
    "FootballLeagueStack",
    # Hard-code account+region or leave as env defaults:
    # env=cdk.Environment(account="123456789012", region="ap-southeast-1"),
)

app.synth()
