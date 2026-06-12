from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://localhost/football_league"
    # Used for JWT signing later. Must be overridden in production via .env.
    secret_key: str = "changeme-insecure-default"

    # ------------------------------------------------------------------
    # Phase 4 — S3 / CloudFront
    #
    # S3_BUCKET_NAME: the name of the private media bucket.
    #   boto3 uses the EC2 IAM role for credentials automatically —
    #   no AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY needed here.
    #
    # CLOUDFRONT_DOMAIN: the *.cloudfront.net domain for serving files.
    #   Example: "d1abc2xyz3.cloudfront.net"
    #   get_file_url() builds: "https://<domain>/<key>"
    #
    # USE_PRESIGNED_URLS: when True, get_file_url() returns a time-limited
    #   S3 presigned GET URL instead of a CloudFront/public URL.
    #   Use this while CloudFront's bucket policy is not yet configured.
    #   The EC2 IAM role must have s3:GetObject on the bucket.
    #   URL lifetime is controlled by PRESIGNED_URL_EXPIRY_SECONDS.
    #
    # AWS_REGION: the region the S3 bucket lives in.
    #   Must match the region the EC2 instance is running in to avoid
    #   cross-region transfer costs and reduce latency.
    # ------------------------------------------------------------------
    s3_bucket_name: str = ""
    cloudfront_domain: str = ""
    use_presigned_urls: bool = False
    presigned_url_expiry_seconds: int = 3600
    aws_region: str = "ap-southeast-1"

    # ------------------------------------------------------------------
    # Phase 5 — SQS notification queue
    # ------------------------------------------------------------------
    # SQS notification queue — injected from CDK via .env on EC2.
    # Left empty by default so local dev and tests skip SQS calls silently.
    sqs_queue_url: str = ""

    # Cognito — injected from CDK via .env on EC2.
    # Left empty by default; get_current_user raises 401 when not configured
    # (preventing unauthenticated access to all protected endpoints).
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "ap-southeast-1"
    # Derived from pool ID: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json
    # Stored explicitly so it can be overridden in tests without a real pool.
    cognito_jwks_url: str = ""

    # ------------------------------------------------------------------
    # Phase 7 — CloudWatch observability
    #
    # CLOUDWATCH_NAMESPACE: custom metric namespace for PutMetricData.
    #   Set to "FootballLeague" on EC2 (injected by CDK).
    #   Left empty by default — middleware skips PutMetricData when unset,
    #   keeping local dev and tests clean without mocking boto3.
    # ------------------------------------------------------------------
    cloudwatch_namespace: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
