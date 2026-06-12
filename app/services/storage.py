"""
S3 / CloudFront storage service.

All three public functions are called by the routers; the routers never
import boto3 directly.  Keeping boto3 behind this module boundary means
tests can patch a single import point ("app.services.storage.boto3") to
replace all AWS calls with mocks — no real network calls needed in CI.

Upload flow (enforced here):
  1. Router calls generate_upload_url(folder, filename, content_type).
     Returns {"url", "fields", "key", "expires_in"}.
  2. Client POSTs directly to S3 using the url + fields (never through API).
  3. Client sends the returned "key" back to the API.
  4. Router calls get_file_url(key) to build the CloudFront URL for
     storage in the database.

Deletion flow:
  Router calls delete_file(key) before overwriting a logo / photo or
  when a record is deleted.

boto3 credentials:
  When running on EC2 with an IAM role, boto3 fetches temporary credentials
  from the instance metadata service automatically (no env vars needed).
  Locally, boto3 falls back to ~/.aws/credentials (aws configure).
  Neither case requires hardcoded keys in this file or in .env.
"""

from __future__ import annotations

import uuid
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status

from app.config import settings


def _s3_client() -> Any:
    """
    Creates a boto3 S3 client pinned to the configured region.

    We set endpoint_url explicitly so that generate_presigned_post returns a
    regional URL (e.g. s3.ap-southeast-1.amazonaws.com).  Without this,
    boto3 uses the global s3.amazonaws.com endpoint and S3 returns a 307
    redirect — presigned URLs cannot be followed because the signature is
    bound to the original URL, not the redirect target.
    """
    region = settings.aws_region or "us-east-1"
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
    )


def generate_upload_url(
    folder: str,
    filename: str,
    content_type: str,
) -> dict[str, object]:
    """
    Generate a pre-signed POST URL that lets the client upload one file
    directly to S3 without routing the bytes through the API.

    WHY PRE-SIGNED POST (not PUT):
      POST allows server-enforced conditions embedded in a signed policy:
        - key must equal the UUID key we generated (prevents redirect attacks)
        - Content-Type must match what the client declared
        - File size must be between 1 byte and 10 MB
      A pre-signed PUT URL has no such conditions — the client can upload
      any content type and any size.

    WHY UUID IN THE KEY:
      Without a UUID, two uploads of "logo.jpg" would overwrite each other.
      With a UUID, every upload gets a globally unique key.
      The original filename is preserved separately (in file_name column)
      for display purposes.

    Args:
        folder:       S3 "folder" prefix, e.g. "clubs/logos" or
                      "releases/documents".  No leading or trailing slash.
        filename:     Original filename from the client, e.g. "logo.jpg".
                      Used only to extract the file extension.
        content_type: MIME type declared by the client, e.g. "image/jpeg".
                      Embedded in the signed policy — S3 rejects uploads
                      that don't send this exact Content-Type header.

    Returns a dict with four keys:
        url      — S3 endpoint to POST to
                   (e.g. "https://bucket.s3.ap-southeast-1.amazonaws.com/")
        fields   — dict of form fields to include in the multipart POST
                   (signed policy, credential, Content-Type, key, etc.)
                   These MUST be included before the file field in the form.
        key      — the S3 object key that will be created on upload
                   (e.g. "clubs/logos/a1b2c3d4-…-e5f6.jpg")
                   Store this in the database after a successful upload.
        expires_in — URL validity in seconds (900 = 15 minutes)
    """
    # Build a key that is unguessable and unique.
    # We extract the original extension so the stored object has the same
    # MIME hint as the original file (useful for debugging in S3 console).
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    key = f"{folder}/{uuid.uuid4()}.{ext}"

    if not settings.s3_bucket_name:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "File storage is not configured on this server.",
        )

    client = _s3_client()
    try:
        response = client.generate_presigned_post(
            Bucket=settings.s3_bucket_name,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"key": key},
                {"Content-Type": content_type},
                ["content-length-range", 1, 10 * 1024 * 1024],
            ],
            ExpiresIn=900,
        )
    except (ClientError, BotoCoreError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Storage service error: {exc}",
        ) from exc

    return {
        "url": response["url"],
        "fields": response["fields"],
        "key": key,
        "expires_in": 900,
    }


def get_file_url(object_key: str) -> str:
    """
    Build the public URL for serving a stored S3 object.

    Priority:
      1. CloudFront  — if CLOUDFRONT_DOMAIN is set (recommended for production).
         The bucket should be private; CloudFront authenticates via OAC.
      2. Direct S3   — if S3_BUCKET_NAME is set but CLOUDFRONT_DOMAIN is not.
         Requires the bucket to have a public GetObject bucket policy.
      3. Raw key     — last resort; local dev with no AWS config at all.

    Args:
        object_key: S3 object key stored in the database,
                    e.g. "clubs/logos/a1b2c3.jpg"

    Returns one of:
        "https://d1abc2.cloudfront.net/clubs/logos/a1b2c3.jpg"          (CF)
        "https://bucket.s3.ap-southeast-1.amazonaws.com/…/a1b2c3.jpg"  (S3)
    """
    domain = settings.cloudfront_domain.strip()
    # Guard: strip accidental https:// prefix in env var
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]

    if domain:
        return f"https://{domain}/{object_key}"

    # No CloudFront — fall back to a direct virtual-hosted S3 URL.
    # Requires the bucket to allow public GetObject (see deployment docs).
    if settings.s3_bucket_name:
        region = settings.aws_region or "us-east-1"
        return (
            f"https://{settings.s3_bucket_name}.s3.{region}.amazonaws.com/{object_key}"
        )

    # No AWS at all — local dev only, return raw key so nothing crashes.
    return object_key


def delete_file(object_key: str) -> None:
    """
    Delete an object from S3.

    Called when:
      - A club logo is replaced (delete old key before storing new key)
      - A player photo is replaced
      - A release is cancelled and the document should be removed

    Note: with versioning enabled on the bucket, delete_object creates a
    delete marker rather than removing the bytes immediately.  The object
    is still recoverable from the S3 console until the version is
    permanently deleted or a lifecycle rule expires it.

    Args:
        object_key: S3 object key to delete, e.g. "clubs/logos/a1b2c3.jpg"
    """
    client = _s3_client()
    client.delete_object(
        Bucket=settings.s3_bucket_name,
        Key=object_key,
    )
