-- =============================================================================
-- DB Admin Commands
-- Run on EC2:  psql $DATABASE_URL -f scripts/db_admin.sql
-- Or interactively: psql $DATABASE_URL
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. DELETE ALL USERS AND CLUBS EXCEPT THE SUPER ADMIN
--    Run each block in order — FK constraints require this sequence.
-- -----------------------------------------------------------------------------

BEGIN;

-- Wipe governance roles for non-super-admin users
DELETE FROM user_governance_roles
WHERE user_id IN (
    SELECT id FROM users WHERE role != 'super_admin'
);

-- Wipe audit logs that reference non-super-admin users (optional — remove if you want to keep audit trail)
-- DELETE FROM audit_logs WHERE actor_id IN (SELECT id FROM users WHERE role != 'super_admin');

-- Wipe notifications
DELETE FROM notifications
WHERE user_id IN (
    SELECT id FROM users WHERE role != 'super_admin'
);

-- Wipe notification preferences
DELETE FROM notification_preferences
WHERE user_id IN (
    SELECT id FROM users WHERE role != 'super_admin'
);

-- Wipe club membership requests
DELETE FROM club_membership_requests;

-- Wipe registration requests
DELETE FROM registration_requests;

-- Wipe player season registrations
DELETE FROM player_season_registrations;

-- Wipe release documents
DELETE FROM release_documents;

-- Wipe releases
DELETE FROM player_releases;

-- Wipe club season comments
DELETE FROM club_season_comments;

-- Wipe unlock approvals (child of club_unlock_requests)
DELETE FROM unlock_approvals;

-- Wipe club unlock requests
DELETE FROM club_unlock_requests;

-- Wipe club season profiles
DELETE FROM club_season_profiles;

-- Wipe club staff
DELETE FROM club_staff;

-- Clear official player links on clubs and league_info before deleting players
UPDATE clubs SET
    president_player_id = NULL,
    secretary_player_id = NULL,
    treasurer_player_id = NULL;

UPDATE league_info SET
    president_player_id = NULL,
    secretary_player_id = NULL,
    treasurer_player_id = NULL;

-- Wipe players
DELETE FROM players;

-- Wipe non-super-admin users
DELETE FROM users WHERE role != 'super_admin';

-- Wipe all clubs
DELETE FROM clubs;

COMMIT;

-- Verify
SELECT id, email, role FROM users;
SELECT COUNT(*) AS clubs_remaining FROM clubs;


-- -----------------------------------------------------------------------------
-- 2. CHANGE SUPER ADMIN EMAIL AND PASSWORD
--    Replace the values in <angle brackets> before running.
-- -----------------------------------------------------------------------------

-- 2a. Update the email in the DB
BEGIN;
UPDATE users
SET email = '<new-email@example.com>'
WHERE role = 'super_admin';
COMMIT;

-- 2b. Update email + reset password in Cognito (run on EC2, requires AWS CLI)
--     Replace USER_POOL_ID, OLD_EMAIL, NEW_EMAIL, NEW_PASSWORD as needed.

-- Step 1: Update the email attribute in Cognito
-- aws cognito-idp admin-update-user-attributes \
--     --user-pool-id <USER_POOL_ID> \
--     --username <OLD_EMAIL> \
--     --user-attributes Name=email,Value=<NEW_EMAIL> Name=email_verified,Value=true

-- Step 2: Set a new temporary password (user will be forced to change on next login)
-- aws cognito-idp admin-set-user-password \
--     --user-pool-id <USER_POOL_ID> \
--     --username <OLD_EMAIL> \
--     --password '<NEW_PASSWORD>' \
--     --permanent false

-- NOTE: Cognito username = original email used at creation (it doesn't auto-update
-- when you change the email attribute). If you need to change the Cognito username
-- itself you must delete and recreate the Cognito user — contact Ravin before doing this.
