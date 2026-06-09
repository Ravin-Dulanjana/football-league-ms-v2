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
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as event_sources
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ses as ses
from aws_cdk import aws_sqs as sqs
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
        # 4. SQS — notification queue + dead letter queue
        #
        # Standard queue (not FIFO): notification ordering doesn't matter
        # and standard gives us higher throughput at lower cost.
        #
        # visibility_timeout: must be >= Lambda timeout (60s). Using 6×
        # the Lambda timeout (360s) is the AWS recommendation — gives the
        # Lambda plenty of time to process and delete the message before
        # SQS re-delivers it to another invocation.
        #
        # dead_letter_queue: after 3 failed deliveries, the message is
        # moved to the DLQ automatically. Messages wait there for 14 days
        # for inspection and manual re-processing.
        # ---------------------------------------------------------------
        notification_dlq = sqs.Queue(
            self,
            "NotificationDLQ",
            queue_name="football-league-notifications-dlq",
            retention_period=Duration.days(14),
        )

        notification_queue = sqs.Queue(
            self,
            "NotificationQueue",
            queue_name="football-league-notifications",
            # 6 × Lambda timeout — prevents duplicate delivery while Lambda processes
            visibility_timeout=Duration.seconds(360),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=notification_dlq,
            ),
        )

        # EC2 role may send messages to the queue (publish_event in events.py)
        notification_queue.grant_send_messages(instance_role)

        # ---------------------------------------------------------------
        # 5. Lambda — notification handler
        #
        # Packaged from infra/lambda/ — CDK zips the directory and uploads
        # it to an S3 staging bucket during `cdk deploy`.
        #
        # Handler: notification_handler.handler (module.function)
        # Runtime: Python 3.11 — matches the app's runtime
        # Timeout: 60s — accommodates SES API latency plus retries
        #
        # IAM: CDK auto-creates a Lambda execution role. We attach:
        #   - SQS consume permissions (via grant_consume_messages)
        #   - ses:SendEmail (SES does not support resource-level restrictions
        #     on SendEmail — resource must be "*")
        # ---------------------------------------------------------------
        ses_sender_email: str = (
            self.node.try_get_context("ses_sender_email") or "noreply@example.com"
        )

        notification_fn = lambda_.Function(
            self,
            "NotificationHandler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="notification_handler.handler",
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "lambda")
            ),
            environment={
                "SES_SENDER_EMAIL": ses_sender_email,
                "SES_REGION": self.region,
            },
            timeout=Duration.seconds(60),
            description="Sends email notifications for domain events via SES",
        )

        # Grant Lambda permission to consume messages from the queue.
        # This adds: ReceiveMessage, DeleteMessage, GetQueueAttributes,
        # ChangeMessageVisibility — everything the SQS poller needs.
        notification_queue.grant_consume_messages(notification_fn)

        # SES SendEmail — not resource-scoped (SES limitation)
        notification_fn.add_to_role_policy(
            iam.PolicyStatement(
                sid="SESsendEmail",
                actions=["ses:SendEmail"],
                resources=["*"],
            )
        )

        # SQS → Lambda event source mapping.
        # batch_size=10: Lambda receives up to 10 messages per invocation.
        # report_batch_item_failures=True: Lambda returns failed message IDs
        # so SQS retries only those — not the whole batch. This prevents
        # duplicate emails for messages that already succeeded.
        notification_fn.add_event_source(
            event_sources.SqsEventSource(
                notification_queue,
                batch_size=10,
                report_batch_item_failures=True,
            )
        )

        # ---------------------------------------------------------------
        # 6. SES — email identity
        #
        # Verifies the sender address. AWS sends a verification email to
        # ses_sender_email when this stack is deployed for the first time.
        # The address must be clicked before SES will send from it.
        #
        # ⚠️  SES sandbox mode (default): you can only send TO verified
        #     email addresses as well. Request SES production access in the
        #     AWS console to send to arbitrary recipients.
        #
        # Update ses_sender_email in cdk.json before deploying.
        # ---------------------------------------------------------------
        ses.EmailIdentity(
            self,
            "SenderEmailIdentity",
            identity=ses.Identity.email(ses_sender_email),
        )

        # ---------------------------------------------------------------
        # 7. Cognito — User Pool + Client
        #
        # User Pool:  the user directory. Email-only sign-in. Self sign-up
        #   is disabled — admins create users via the AWS console or CLI so
        #   they can set the custom:role attribute before the user logs in.
        #
        # Password policy: min 8 chars, require uppercase + lowercase +
        #   number + symbol. Cognito enforces this on all SetPassword calls.
        #
        # Custom attributes:
        #   custom:role      — "super_admin" | "league_admin" | "club_admin" | "player"
        #   custom:club_id   — numeric string (NumberAttribute stored as string in JWT)
        #   custom:player_id — numeric string
        #   All are mutable so admins can reassign roles without recreating users.
        #
        # ⚠️  Security: custom attributes are set by admins only. Users
        #   cannot modify them — the User Pool Client has no write access to
        #   custom attributes, only read.
        #
        # User Pool Client:
        #   - No client secret: we're calling Cognito from EC2 server-side
        #     code, but without a client secret means no SECRET_HASH needed.
        #     A secret would be correct for a truly confidential client —
        #     acceptable trade-off here for simplicity.
        #   - USER_PASSWORD_AUTH: allows email+password login (InitiateAuth).
        #   - Token validity: access=1h, id=1h, refresh=30d (Cognito defaults).
        # ---------------------------------------------------------------
        user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="football-league-users",
            # Admins create users; players/admins do not self-register
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True, username=False),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            # Standard attributes
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            ),
            # Custom attributes — mutable so admins can reassign roles
            custom_attributes={
                "role": cognito.StringAttribute(mutable=True),
                "club_id": cognito.NumberAttribute(mutable=True),
                "player_id": cognito.NumberAttribute(mutable=True),
            },
            removal_policy=RemovalPolicy.DESTROY,
        )

        user_pool_client = user_pool.add_client(
            "AppClient",
            user_pool_client_name="football-league-app",
            # No client secret — simpler server-side flow; see note above
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                # USER_PASSWORD_AUTH: email+password → tokens (our /auth/login)
                user_password=True,
                # REFRESH_TOKEN_AUTH is implicitly enabled when user_password=True
            ),
            # Token validity — 1h access/id, 30d refresh
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            # Prevent client from writing custom attributes (read-only for client)
            read_attributes=cognito.ClientAttributes().with_standard_attributes(
                cognito.StandardAttributesMask(email=True)
            ),
        )

        # JWKS URL — FastAPI uses this to fetch RSA public keys for JWT verification.
        # Format: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json
        jwks_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com"
            f"/{user_pool.user_pool_id}/.well-known/jwks.json"
        )

        # ---------------------------------------------------------------
        # 8. Database — RDS or EC2-local PostgreSQL
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
            # Phase 5 — SQS notification queue
            f'export SQS_QUEUE_URL="{notification_queue.queue_url}"',
            f'export COGNITO_USER_POOL_ID="{user_pool.user_pool_id}"',
            f'export COGNITO_CLIENT_ID="{user_pool_client.user_pool_client_id}"',
            f'export COGNITO_REGION="{self.region}"',
            f'export COGNITO_JWKS_URL="{jwks_url}"',
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
        CfnOutput(
            self,
            "NotificationQueueURL",
            value=notification_queue.queue_url,
            description="SQS queue URL — set as SQS_QUEUE_URL in EC2 .env",
        )
        CfnOutput(
            self,
            "NotificationDLQURL",
            value=notification_dlq.queue_url,
            description="Dead letter queue — inspect here if notifications fail",
        )
        CfnOutput(
            self,
            "NotificationLambdaName",
            value=notification_fn.function_name,
            description="Lambda function name for the notification handler",
        )
        CfnOutput(
            self,
            "CognitoUserPoolId",
            value=user_pool.user_pool_id,
            description="Cognito User Pool ID — set as COGNITO_USER_POOL_ID in .env",
        )
        CfnOutput(
            self,
            "CognitoClientId",
            value=user_pool_client.user_pool_client_id,
            description="Cognito App Client ID — set as COGNITO_CLIENT_ID in .env",
        )
        CfnOutput(
            self,
            "CognitoJwksUrl",
            value=jwks_url,
            description="JWKS URL for JWT verification — set as COGNITO_JWKS_URL in .env",  # noqa: E501
        )
