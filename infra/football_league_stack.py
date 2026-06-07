"""
Football League MS — AWS CDK Stack

Provisioned resources depend on the `use_rds` context flag (cdk.json):

  use_rds=true  (full AWS account):
    VPC, EC2, RDS PostgreSQL 15, IAM role, security groups
    PostgreSQL lives in a private subnet managed by AWS.

  use_rds=false (restricted/free-plan account — current default):
    VPC, EC2, IAM role, EC2 security group
    PostgreSQL is installed directly on the EC2 by user_data.sh.
    Architecture is identical from the app's perspective — just no RDS.

To switch modes:
  cdk.json  →  "use_rds": "true"    (requires a real AWS account with RDS access)
  cdk.json  →  "use_rds": "false"   (works on any account — PostgreSQL on EC2)
"""

from __future__ import annotations

import os

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from constructs import Construct


class FootballLeagueStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------
        # Context flags
        # ---------------------------------------------------------------
        # use_rds: "true"  → create an RDS instance (requires full AWS account)
        #          "false" → install PostgreSQL on EC2 (works on any account)
        use_rds: bool = self.node.try_get_context("use_rds") == "true"

        # ---------------------------------------------------------------
        # 1. VPC
        #
        # max_azs=2  — RDS subnet groups require subnets in ≥2 AZs. We keep
        #              2 AZs even in EC2-local mode so switching to RDS later
        #              requires no VPC changes.
        # nat_gateways=0 — NAT gateways cost ~$32/month. EC2 is in a PUBLIC
        #              subnet (reaches internet via IGW); the private subnet is
        #              only used when use_rds=true.
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
        # ⚠️  PRODUCTION NOTE: Port 22 open to 0.0.0.0/0 is a security risk.
        # Restrict to your IP: ec2.Peer.ipv4("YOUR.IP.HERE/32")
        # Or remove SSH entirely and use SSM Session Manager.
        # ---------------------------------------------------------------
        ec2_sg = ec2.SecurityGroup(
            self,
            "EC2SecurityGroup",
            vpc=vpc,
            description="Football League EC2 - allow HTTP, HTTPS, SSH",
            allow_all_outbound=True,
        )
        ec2_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(22),
            "SSH - restrict to your IP before production",
        )
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")

        # ---------------------------------------------------------------
        # 3. IAM Role for EC2
        #
        # S3 access is always included (file uploads, Phase 3).
        # Secrets Manager access is only added in RDS mode (fetching the
        # auto-generated RDS password at boot).
        # ---------------------------------------------------------------
        instance_role = iam.Role(
            self,
            "EC2InstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Football League EC2 role",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
            ],
        )
        instance_role.add_to_policy(
            iam.PolicyStatement(
                sid="S3Access",
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=["*"],  # Tighten to bucket ARN before production
            )
        )

        # ---------------------------------------------------------------
        # 4. Database — RDS or EC2-local PostgreSQL
        # ---------------------------------------------------------------
        db_host: str
        db_port: str
        secret_arn: str
        db_user: str

        if use_rds:
            # -----------------------------------------------------------
            # RDS mode: managed PostgreSQL in a private subnet.
            #
            # Security group: port 5432 only from the EC2 SG, not any IP.
            # Credentials: auto-generated by CDK, stored in Secrets Manager.
            #   EC2 fetches the password at boot via the IAM role — the
            #   password never appears in code or on disk.
            # publicly_accessible=False: RDS has no public DNS name.
            # -----------------------------------------------------------
            rds_sg = ec2.SecurityGroup(
                self,
                "RDSSecurityGroup",
                vpc=vpc,
                description="Football League RDS - PostgreSQL from EC2 only",
                allow_all_outbound=False,
            )
            rds_sg.add_ingress_rule(
                ec2_sg,
                ec2.Port.tcp(5432),
                "PostgreSQL - EC2 security group only",
            )

            db_instance = rds.DatabaseInstance(
                self,
                "RDS",
                engine=rds.DatabaseInstanceEngine.postgres(
                    version=rds.PostgresEngineVersion.VER_15
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
                multi_az=False,
                allocated_storage=20,
                publicly_accessible=False,
                deletion_protection=False,  # Set True before production
                removal_policy=RemovalPolicy.DESTROY,  # Set RETAIN before production
            )

            if db_instance.secret:
                db_instance.secret.grant_read(instance_role)

            db_host = db_instance.db_instance_endpoint_address
            db_port = db_instance.db_instance_endpoint_port
            db_user = "postgres"
            secret_arn = db_instance.secret.secret_arn if db_instance.secret else ""

        else:
            # -----------------------------------------------------------
            # EC2-local mode: PostgreSQL installs on the same EC2 instance.
            #
            # user_data.sh detects USE_RDS=false and:
            #   1. Installs PostgreSQL 15 from the official PGDG repo
            #   2. Initialises the cluster and configures password auth
            #   3. Creates the football_league database and user
            #   4. Generates a random password stored only in .env
            #
            # Architecture is identical from the app's perspective —
            # DATABASE_URL just points to localhost instead of an RDS hostname.
            # To migrate to RDS later: set use_rds=true in cdk.json,
            # pg_dump from EC2, pg_restore to RDS, redeploy.
            # -----------------------------------------------------------
            db_host = "localhost"
            db_port = "5432"
            db_user = "postgres"
            secret_arn = ""

        # ---------------------------------------------------------------
        # 5. EC2 User Data
        #
        # Variables injected here are shell exports that user_data.sh reads.
        # CDK token resolution: when use_rds=true, db_host is a CloudFormation
        # GetAtt reference that resolves to the RDS hostname at deploy time.
        # ---------------------------------------------------------------
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            f'export USE_RDS="{"true" if use_rds else "false"}"',
            'export APP_DIR="/opt/football-league"',
            "export REPO_URL="
            '"https://github.com/Ravin-Dulanjana/football-league-ms-v2.git"',
            f'export DB_HOST="{db_host}"',
            f'export DB_PORT="{db_port}"',
            'export DB_NAME="football_league"',
            f'export DB_USER="{db_user}"',
            f'export SECRET_ARN="{secret_arn}"',
        )

        script_path = os.path.join(os.path.dirname(__file__), "user_data.sh")
        with open(script_path) as f:
            user_data.add_commands(*f.read().split("\n"))

        # ---------------------------------------------------------------
        # 6. EC2 Instance
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
            # t3.micro is the free-tier eligible instance in ap-southeast-1.
            # t2.micro is not available on restricted free-plan accounts.
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=ec2_sg,
            role=instance_role,
            user_data=user_data,
            key_pair=key_pair,
        )

        # In RDS mode, wait for the database before EC2 boots
        if use_rds:
            instance.node.add_dependency(db_instance)  # type: ignore[possibly-undefined]

        # ---------------------------------------------------------------
        # 7. Stack Outputs
        # ---------------------------------------------------------------
        CfnOutput(
            self,
            "EC2PublicIP",
            value=instance.instance_public_ip,
            description="EC2 public IP - test: curl http://<ip>/clubs/",
        )
        CfnOutput(
            self,
            "EC2PublicDNS",
            value=instance.instance_public_dns_name,
            description="EC2 public DNS name",
        )
        CfnOutput(
            self,
            "DBMode",
            value="rds" if use_rds else "ec2-local",
            description="Database mode: rds=managed RDS, ec2-local=PostgreSQL on EC2",
        )
        if use_rds:
            CfnOutput(
                self,
                "RDSEndpoint",
                value=db_instance.db_instance_endpoint_address,  # type: ignore[possibly-undefined]
                description="RDS hostname - only reachable from inside VPC",
            )
            CfnOutput(
                self,
                "RDSSecretARN",
                value=(
                    db_instance.secret.secret_arn  # type: ignore[possibly-undefined]
                    if db_instance.secret  # type: ignore[possibly-undefined]
                    else "n/a"
                ),
                description="Secrets Manager ARN for RDS credentials",
            )
        CfnOutput(
            self,
            "SSMConnectCommand",
            value=f"aws ssm start-session --target {instance.instance_id}",
            description="Connect via SSM Session Manager (no SSH key required)",
        )
