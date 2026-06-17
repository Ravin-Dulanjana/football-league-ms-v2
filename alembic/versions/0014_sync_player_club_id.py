"""sync player club_id to users table

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-17

One-time data fix: for every player-role user whose user.club_id does not
match the club_id on their linked Player record, copy the Player value into
users.club_id.  This repairs rows that were never synced and rows corrupted
by the bug in PR #86 (since repaired for admins in #87/#88, but player-role
users may still be out of sync in environments that were not self-healed by
the get_me endpoint or a league-admin users-list request).
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET club_id = players.club_id
        FROM players
        WHERE users.player_id = players.id
          AND users.role = 'player'
          AND players.club_id IS NOT NULL
          AND (users.club_id IS DISTINCT FROM players.club_id)
        """
    )


def downgrade() -> None:
    pass
