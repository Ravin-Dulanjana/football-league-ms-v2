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

Phase 4 additions (all modes):
    S3 bucket — private, versioned, Block All Public Access
    CloudFront distribution — OAC so CloudFront is the only entity that
      can read from S3; clients never hit the bucket directly
    IAM role S3 policy — scoped to this specific bucket (was resources=["*"])

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
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
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
        # 3. S3 Media Bucket — private, versioned, Block All Public Access
        #
        # WHY PRIVATE:
        #   Release documents are legal records. If the bucket is public,
        #   anyone who guesses a key can download the file.
        #   All public reads go through CloudFront (see section 4), which
        #   authenticates to S3 via OAC — the bucket never serves directly.
        #
        # WHY VERSIONING:
        #   Protects against accidental deletion. If a file is overwritten
        #   or deleted, previous versions are recoverable.
        #   ⚠️  Add a lifecycle rule in production to expire non-current
        #   versions after 30 days — otherwise storage costs grow forever.
        #
        # enforce_ssl=True:
        #   Denies any request that is not made over HTTPS (adds a bucket
        #   policy condition: aws:SecureTransport = true).
        # ---------------------------------------------------------------
        media_bucket = s3.Bucket(
            self,
            "MediaBucket",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            enforce_ssl=True,
            cors=[
                s3.CorsRule(
                    # CORS is required for browser-based pre-signed POST uploads.
                    # The browser makes a cross-origin POST to s3.amazonaws.com;
                    # without CORS, the browser blocks the response.
                    # Restrict allowed_origins to your domain before production.
                    allowed_headers=["*"],
                    allowed_methods=[s3.HttpMethods.POST, s3.HttpMethods.PUT],
                    allowed_origins=["*"],
                    max_age=3000,
                )
            ],
        )

        # ---------------------------------------------------------------
        # 4. CloudFront Distribution with OAC
        #
        # OAC (Origin Access Control) — the modern replacement for OAI.
        # S3BucketOrigin.with_origin_access_control() (CDK ≥ 2.177):
        #   - Creates an OAC resource automatically
        #   - Grants CloudFront distribution a signed SigV4 identity
        #   - Adds a bucket policy: allow s3:GetObject only from this
        #     specific CloudFront distribution (pinned by distribution ARN)
        #
        # WHY OAC instead of making the bucket public:
        #   A public bucket is reachable directly at
        #   bucket.s3.amazonaws.com — any link sharer can expose files.
        #   With OAC, requests to s3.amazonaws.com return 403; only
        #   requests routed through CloudFront succeed.
        #
        # CACHING_OPTIMIZED cache policy:
        #   Caches GET/HEAD responses, respects Cache-Control headers.
        #   Serves subsequent reads from the nearest edge location,
        #   reducing S3 GET costs and improving global latency.
        # ---------------------------------------------------------------
        distribution = cloudfront.Distribution(
            self,
            "CDN",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(media_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
            ),
            comment="Football League media CDN",
        )

        # ---------------------------------------------------------------
        # 5. IAM Role for EC2
        #
        # S3 policy is now SCOPED to the media bucket (was resources=["*"]).
        # Principle of least privilege: the EC2 can only operate on objects
        # inside the football-league media bucket.
        #
        # Secrets Manager access is only added in RDS mode.
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
                sid="S3MediaBucketAccess",
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                ],
                # Scope to objects inside the bucket only.
                # media_bucket.bucket_arn             = arn:aws:s3:::bucket-name
                # media_bucket.bucket_arn + "/*"      = arn:aws:s3:::bucket-name/*
                resources=[f"{media_bucket.bucket_arn}/*"],
            )
        )
        instance_role.add_to_policy(
            iam.PolicyStatement(
                sid="S3MediaBucketList",
                actions=["s3:ListBucket"],
                resources=[media_bucket.bucket_arn],
            )
        )

        # ---------------------------------------------------------------
        # 6. Database — RDS or EC2-local PostgreSQL
        # ---------------------------------------------------------------
        db_host: str
        db_port: str
        secret_arn: str
        db_user: str

        if use_rds:
            # -----------------------------------------------------------
            # RDS mode: managed PostgreSQL in a private subnet.
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
                deletion_protection=False,
                removal_policy=RemovalPolicy.DESTROY,
            )

            if db_instance.secret:
                db_instance.secret.grant_read(instance_role)

            db_host = db_instance.db_instance_endpoint_address
            db_port = db_instance.db_instance_endpoint_port
            db_user = "postgres"
            secret_arn = db_instance.secret.secret_arn if db_instance.secret else ""

        else:
            db_host = "localhost"
            db_port = "5432"
            db_user = "postgres"
            secret_arn = ""

        # ---------------------------------------------------------------
        # 7. EC2 User Data
        #
        # S3_BUCKET_NAME and CLOUDFRONT_DOMAIN are injected into .env
        # by user_data.sh so the app can generate presigned URLs and
        # build CloudFront URLs without any hardcoded values in code.
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
            # Phase 4 — S3 / CloudFront
            f'export S3_BUCKET_NAME="{media_bucket.bucket_name}"',
            f'export CLOUDFRONT_DOMAIN="{distribution.distribution_domain_name}"',
        )

        script_path = os.path.join(os.path.dirname(__file__), "user_data.sh")
        with open(script_path) as f:
            user_data.add_commands(*f.read().split("\n"))

        # ---------------------------------------------------------------
        # 8. EC2 Instance
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

        if use_rds:
            instance.node.add_dependency(db_instance)  # type: ignore[possibly-undefined]

        # ---------------------------------------------------------------
        # 9. Stack Outputs
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
        CfnOutput(
            self,
            "MediaBucketName",
            value=media_bucket.bucket_name,
            description="S3 bucket for media files (logos, photos, documents)",
        )
        CfnOutput(
            self,
            "CloudFrontDomain",
            value=distribution.distribution_domain_name,
            description="CloudFront domain for serving media files",
        )
        CfnOutput(
            self,
            "CloudFrontDistributionId",
            value=distribution.distribution_id,
            description="CloudFront distribution ID",
        )
        CfnOutput(
            self,
            "SSMConnectCommand",
            value=f"aws ssm start-session --target {instance.instance_id}",
            description="Connect via SSM Session Manager (no SSH key required)",
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
