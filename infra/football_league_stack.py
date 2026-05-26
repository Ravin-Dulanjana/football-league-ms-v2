"""
Football League MS — AWS CDK Stack

Provisions:
  VPC        1 public subnet (EC2) + 1 private subnet (RDS), spanning 2 AZs
  EC2        t2.micro, Amazon Linux 2023, public subnet
  RDS        PostgreSQL 16, t3.micro, private subnet, no public access
  IAM role   EC2 instance profile with S3 + Secrets Manager access
"""

from __future__ import annotations

import os

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_rds as rds,
)
from constructs import Construct


class FootballLeagueStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------
        # 1. VPC
        #
        # A VPC is your private network slice inside AWS. Every resource we
        # create lives inside it and is invisible to the outside world unless
        # we explicitly open a door.
        #
        # max_azs=2  — RDS subnet groups require subnets in ≥2 AZs, even
        #              for single-AZ instances. Two AZs satisfies that.
        # nat_gateways=0 — NAT gateways cost ~$32/month each. We don't need
        #              one: EC2 is in a PUBLIC subnet (has internet via IGW),
        #              and RDS is PRIVATE_ISOLATED (never needs internet).
        # ---------------------------------------------------------------
        vpc = ec2.Vpc(
            self,
            "VPC",
            max_azs=2,
            nat_gateways=0,
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # ---------------------------------------------------------------
        # 2. Security Group — EC2
        #
        # A security group is a stateful firewall attached to a resource.
        # Stateful = return traffic is automatically allowed; you only need
        # to write inbound rules.
        #
        # ⚠️  PRODUCTION NOTE: Port 22 open to 0.0.0.0/0 is a security risk.
        # Before going live, replace Peer.any_ipv4() with your office/home IP:
        #   ec2.Peer.ipv4("203.0.113.0/32")
        # Or better: remove SSH entirely and use SSM Session Manager (no port
        # needed, access is controlled by IAM instead of a key file).
        # ---------------------------------------------------------------
        ec2_sg = ec2.SecurityGroup(
            self,
            "EC2SecurityGroup",
            vpc=vpc,
            description="Football League EC2 — allow HTTP, HTTPS, SSH",
            allow_all_outbound=True,  # EC2 needs to reach RDS + internet (git, pip)
        )
        ec2_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(22),
            "SSH — restrict to your IP before production",
        )
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")

        # ---------------------------------------------------------------
        # 3. Security Group — RDS
        #
        # Port 5432 is only allowed from the EC2 security group — NOT from
        # any IP. This means only our application server can connect to the
        # database. Even if someone got your DB host + port, they can't
        # connect unless they're already inside the EC2 SG.
        # ---------------------------------------------------------------
        rds_sg = ec2.SecurityGroup(
            self,
            "RDSSecurityGroup",
            vpc=vpc,
            description="Football League RDS — allow PostgreSQL only from EC2",
            allow_all_outbound=False,  # RDS never initiates outbound connections
        )
        rds_sg.add_ingress_rule(
            ec2_sg,
            ec2.Port.tcp(5432),
            "PostgreSQL — EC2 security group only",
        )

        # ---------------------------------------------------------------
        # 4. IAM Role for EC2
        #
        # An IAM role is an identity that AWS services can assume. The EC2
        # instance assumes this role at boot — no credentials file ever lives
        # on disk. We grant:
        #   - AmazonSSMManagedInstanceCore: lets you open a browser-based
        #     shell via Systems Manager Session Manager (no SSH key needed)
        #   - S3 read/write: for file uploads later (replace "*" with your
        #     bucket ARN before production)
        #   - Secrets Manager GetSecretValue: so the boot script can fetch
        #     the RDS password without it ever being in code or on disk
        # ---------------------------------------------------------------
        instance_role = iam.Role(
            self,
            "EC2InstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Football League EC2 role",
            managed_policies=[
                # Enables SSM Session Manager (browser shell, no SSH required)
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
            ],
        )

        # S3 access — tighten to a specific bucket ARN before production
        instance_role.add_to_policy(
            iam.PolicyStatement(
                sid="S3Access",
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=["*"],  # ⚠️ Replace with arn:aws:s3:::your-bucket-name/*
            )
        )

        # ---------------------------------------------------------------
        # 5. RDS PostgreSQL
        #
        # credentials=from_generated_secret: CDK generates a random password
        # and stores it in AWS Secrets Manager automatically. You never see
        # or type the password — the EC2 role fetches it at boot.
        #
        # publicly_accessible=False: RDS won't even get a public DNS name.
        # Only resources inside the VPC can resolve or reach it.
        #
        # deletion_protection=False + DESTROY policy: fine for development.
        # Set both to True before production — you don't want a typo in
        # `cdk destroy` to wipe your production database.
        # ---------------------------------------------------------------
        db_instance = rds.DatabaseInstance(
            self,
            "RDS",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_3
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[rds_sg],
            database_name="football_league",
            credentials=rds.Credentials.from_generated_secret(
                "postgres",
                secret_name="football-league-rds-credentials",
            ),
            multi_az=False,  # single-AZ is fine for development
            allocated_storage=20,  # GB — minimum allowed
            publicly_accessible=False,
            deletion_protection=False,  # ⚠️ set True before production
            removal_policy=RemovalPolicy.DESTROY,  # ⚠️ set RETAIN before production
        )

        # Grant the EC2 role permission to read the RDS secret
        if db_instance.secret:
            db_instance.secret.grant_read(instance_role)

        # ---------------------------------------------------------------
        # 6. EC2 User Data
        #
        # User data is a shell script that runs ONCE on first boot as root.
        # We inject the RDS endpoint and secret ARN as shell variables at the
        # top, then load the main setup script from user_data.sh.
        #
        # CDK resolves db_instance.db_instance_endpoint_address at deploy time
        # to the actual RDS hostname (a CloudFormation Ref/GetAtt reference).
        # ---------------------------------------------------------------
        user_data = ec2.UserData.for_linux()

        # Inject resolved CDK values as environment variables
        user_data.add_commands(
            'export APP_DIR="/opt/football-league"',
            'export REPO_URL="https://github.com/Ravin-Dulanjana/football-league-ms-v2.git"',
            f'export DB_HOST="{db_instance.db_instance_endpoint_address}"',
            f'export DB_PORT="{db_instance.db_instance_endpoint_port}"',
            'export DB_NAME="football_league"',
            'export DB_USER="postgres"',
            f'export SECRET_ARN="'
            f'{db_instance.secret.secret_arn if db_instance.secret else ""}"',
        )

        # Load the rest of the setup script
        script_path = os.path.join(os.path.dirname(__file__), "user_data.sh")
        with open(script_path) as f:
            script_body = f.read()
            # Skip the shebang — user_data.add_commands adds its own header
            script_lines = script_body.split("\n")
            user_data.add_commands(*script_lines)

        # ---------------------------------------------------------------
        # 7. EC2 Instance
        #
        # key_pair_name is read from CDK context so you can pass it at
        # deploy time:  cdk deploy -c key_pair_name=my-key
        # If not set, SSH won't work but SSM Session Manager will.
        # ---------------------------------------------------------------
        key_pair_name: str = self.node.try_get_context("key_pair_name") or ""
        key_pair = (
            ec2.KeyPair.from_key_pair_name(self, "KeyPair", key_pair_name)
            if key_pair_name
            else None
        )

        instance = ec2.Instance(
            self,
            "EC2",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T2, ec2.InstanceSize.MICRO
            ),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=ec2_sg,
            role=instance_role,
            user_data=user_data,
            key_pair=key_pair,
        )

        # Ensure RDS is fully created before EC2 boots and tries to migrate
        instance.node.add_dependency(db_instance)

        # ---------------------------------------------------------------
        # 8. Stack Outputs
        # ---------------------------------------------------------------
        CfnOutput(
            self,
            "EC2PublicIP",
            value=instance.instance_public_ip,
            description="EC2 public IP — test with: curl http://<ip>/clubs/",
        )
        CfnOutput(
            self,
            "EC2PublicDNS",
            value=instance.instance_public_dns_name,
            description="EC2 public DNS name",
        )
        CfnOutput(
            self,
            "RDSEndpoint",
            value=db_instance.db_instance_endpoint_address,
            description="RDS hostname — only reachable from inside the VPC",
        )
        CfnOutput(
            self,
            "RDSSecretARN",
            value=db_instance.secret.secret_arn if db_instance.secret else "n/a",
            description="Secrets Manager ARN for RDS credentials",
        )
        CfnOutput(
            self,
            "SSMConnectCommand",
            value=f"aws ssm start-session --target {instance.instance_id}",
            description="Connect via SSM Session Manager (no SSH key required)",
        )
