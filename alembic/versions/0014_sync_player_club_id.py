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
    # Fix player-role users whose user.club_id was never set or drifted from
    # the linked Player record.
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
    # Fix governance-role users (club_admin OR league_admin+club_admin) whose
    # user.club_id is NULL but have a club_admin entry in user_governance_roles.
    # Affects league_admin users who also hold a club_admin role — their
    # user.role is "league_admin" (highest_role wins) so the club_admin-only
    # heal in attach_governance_roles never fired for them.
    op.execute(
        """
        UPDATE users
        SET club_id = ugr.club_id
        FROM user_governance_roles ugr
        WHERE users.id = ugr.user_id
          AND ugr.role = 'club_admin'
          AND ugr.club_id IS NOT NULL
          AND users.club_id IS NULL
          AND users.role IN ('club_admin', 'league_admin')
        """
    )


def downgrade() -> None:
    pass
