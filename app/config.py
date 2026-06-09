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
    # AWS_REGION: the region the S3 bucket lives in.
    #   Must match the region the EC2 instance is running in to avoid
    #   cross-region transfer costs and reduce latency.
    # ------------------------------------------------------------------
    s3_bucket_name: str = ""
    cloudfront_domain: str = ""
    aws_region: str = "ap-southeast-1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
