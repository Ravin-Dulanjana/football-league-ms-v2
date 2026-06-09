"""Phase 4 — rename file URL columns to S3 object key columns.

These columns previously stored arbitrary URL strings (or placeholder
values).  They now store S3 object keys (e.g. "clubs/logos/uuid.jpg").
The CloudFront URL is built at read time by storage.get_file_url().

Columns renamed:
  clubs.logo_url      → clubs.logo_key
  players.photo_url   → players.photo_key
  release_documents.file_url → release_documents.s3_key

Data migration note:
  Existing rows with non-null values will keep their current string values.
  Any value that is a full URL (starting with "http") should be treated as
  a legacy URL and will not be served through CloudFront until the record
  is updated with a proper S3 key via the new upload flow.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-09
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # op.alter_column with new_column_name generates:
    #   ALTER TABLE clubs RENAME COLUMN logo_url TO logo_key
    # This is a metadata-only operation in PostgreSQL — no data is moved
    # and no table lock is held for longer than a few milliseconds.
    op.alter_column("clubs", "logo_url", new_column_name="logo_key")
    op.alter_column("players", "photo_url", new_column_name="photo_key")
    op.alter_column("release_documents", "file_url", new_column_name="s3_key")


def downgrade() -> None:
    op.alter_column("release_documents", "s3_key", new_column_name="file_url")
    op.alter_column("players", "photo_key", new_column_name="photo_url")
    op.alter_column("clubs", "logo_key", new_column_name="logo_url")
