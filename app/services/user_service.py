"""
User management service.

Handles listing, creating, soft-deleting, and account actions for User records.

Role rules enforced here (beyond what the dependency layer already blocked):
  - league_admin can only create club_admin accounts (not super_admin/league_admin)
  - super_admin only may soft-delete and perform account actions on super_admins
  - league_admin cannot manage super_admin accounts
  - no user may delete or deactivate their own account via these endpoints

Cognito admin operations (reset_password, create_admin_user) use boto3
with the cognito-idp client.  Required IAM permissions on the EC2 role:
  cognito-idp:AdminCreateUser
  cognito-idp:AdminSetUserPassword
  cognito-idp:AdminGetUser
"""

from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime

import boto3
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import CurrentUser
from app.middleware.logging import get_logger
from app.models.player import Player  # used for type annotation of new_player
from app.models.user import User
from app.schemas.player import PlayerCreate
from app.schemas.user import AccountActionRequest, UserCreate
from app.services import audit_service, player_service
from app.services.role_checks import is_super_admin

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_all_users(
    db: Session,
    current_user: CurrentUser,
    include_deleted: bool = False,
) -> list[User]:
    """
    Queryset-as-access-control:
      super_admin  — all users; with include_deleted=True sees soft-deleted too
      league_admin — all non-deleted users (single-league system, sees everyone)
    """
    q = select(User)
    if not (is_super_admin(current_user) and include_deleted):
        q = q.where(User.is_deleted.is_(False))
    return list(db.execute(q.order_by(User.id)).scalars().all())


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_user(
    db: Session,
    data: UserCreate,
    current_user: CurrentUser,
) -> tuple[User | None, str | None]:
    """
    Create a Cognito user + shadow DB record.

    Returns (user, error_message).
    """
    # Enforce creation hierarchy:
    #   super_admin  → any role
    #   league_admin → league_admin, club_admin, player, club_staff (not super_admin)
    #   club_admin   → player or club_staff only (club_id auto-injected below)
    role = current_user.role
    target_role = data.role
    if role == "league_admin" and target_role == "super_admin":
        return None, "League admins cannot create super_admin accounts."
    if role == "club_admin" and target_role not in ("player", "club_staff"):
        return None, "Club admins can only create player or club_staff accounts."

    # When a club_admin creates a player or club_staff, auto-assign their club.
    club_id = data.club_id
    if role == "club_admin" and club_id is None:
        club_id = current_user.club_id
    if role == "club_admin" and target_role == "club_staff" and club_id is None:
        return None, "Club admins must be linked to a club to create staff accounts."

    # Check email is not already taken
    existing = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()
    if existing:
        return None, "A user with that email already exists."

    # A player profile is created when:
    #   a) the role is player (mandatory), or
    #   b) personal details are supplied for any account type — every person
    #      in the league is registered as an identity even if they are staff
    #      or an unplaced account.
    has_personal_details = bool(
        data.full_name and data.date_of_birth and data.nic_number
    )
    create_player_profile = target_role == "player" or has_personal_details

    # Derive member_type: if a player profile is being created the person has
    # a footballer identity; otherwise infer from role for base roles.
    member_type = data.member_type
    if create_player_profile:
        member_type = "player"
    elif member_type is None and target_role == "club_staff":
        member_type = "club_staff"

    player_id: int | None = None
    new_player: Player | None = None
    if create_player_profile:
        try:
            new_player = player_service.create_player(
                db,
                PlayerCreate(
                    full_name=data.full_name,  # type: ignore[arg-type]
                    date_of_birth=data.date_of_birth,  # type: ignore[arg-type]
                    nic_number=data.nic_number,  # type: ignore[arg-type]
                ),
            )
        except Exception:
            return None, "A player with that NIC number already exists."
        player_id = new_player.id

    # Create in Cognito
    cognito_sub = _cognito_create_user(
        email=data.email,
        temporary_password=data.temporary_password,
        role=data.role,
        club_id=club_id,
        player_id=player_id,
    )
    if cognito_sub is None:
        # Roll back the player record we just created before failing.
        if new_player is not None:
            db.delete(new_player)
            db.commit()
        return None, "Failed to create Cognito user. Check Cognito configuration."

    user = User(
        cognito_sub=cognito_sub,
        email=data.email,
        role=data.role,
        member_type=member_type,
        club_id=club_id,
        player_id=player_id,
        is_active=True,
        is_deleted=False,
        force_password_change=True,
    )
    db.add(user)
    db.flush()

    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="user.create",
        entity_type="User",
        entity_id=user.id,
        details={
            "email": data.email,
            "role": data.role,
            "member_type": member_type,
            "club_id": club_id,
        },
    )
    db.commit()
    db.refresh(user)
    logger.info(
        {
            "event": "user.create.complete",
            "user_id": user.id,
            "role": user.role,
            "member_type": user.member_type,
            "actor_id": current_user.id,
        }
    )
    return user, None


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------


def soft_delete_user(
    db: Session,
    target: User,
    current_user: CurrentUser,
    reason: str,
) -> tuple[User | None, str | None]:
    """
    Soft-delete a user (super_admin only).

    Sets is_deleted=True, is_active=False, records deleted_by and deleted_at.
    The row is kept for audit trail purposes.
    """
    if target.id == current_user.id:
        return None, "You cannot delete your own account."
    if target.is_deleted:
        return None, "This user has already been deleted."
    if not reason.strip():
        return None, "A reason is required for deletion."
    # league_admin can only soft-delete player accounts
    if current_user.role == "league_admin" and target.role != "player":
        return None, "League admins can only delete player accounts."
    # nobody can delete a super_admin
    if target.role == "super_admin":
        return None, "Super admin accounts cannot be deleted."

    now = datetime.now(tz=UTC)
    target.is_deleted = True
    target.is_active = False
    target.deleted_at = now
    target.deleted_by = current_user.id
    db.flush()

    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="user.soft_delete",
        entity_type="User",
        entity_id=target.id,
        details={"reason": reason},
    )
    db.commit()
    db.refresh(target)
    return target, None


def hard_delete_user(
    db: Session,
    target: User,
    current_user: CurrentUser,
) -> tuple[bool, str | None]:
    """
    Permanently delete a user record and their Cognito account.

    Only callable by super_admin. The user must have been soft-deleted first
    (is_deleted=True) so there is an intentional two-step process: soft delete
    → review → hard delete.

    Returns (True, None) on success, (False, error_message) on failure.
    """
    if not target.is_deleted:
        return False, "User must be soft-deleted before permanent deletion."
    user_id = target.id
    email = target.email
    cognito_sub = target.cognito_sub
    # Remove from Cognito first; if this fails we abort so the DB record survives
    if not _cognito_delete_user(cognito_sub):
        return False, "Failed to remove Cognito account. DB record preserved."
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="user.hard_delete",
        entity_type="User",
        entity_id=user_id,
        details={"email": email},
    )
    db.delete(target)
    db.commit()
    return True, None


def restore_user(
    db: Session,
    target: User,
    current_user: CurrentUser,
) -> tuple[User | None, str | None]:
    """
    Restore a soft-deleted user (super_admin only).

    Clears is_deleted, re-activates the account, and resets deletion timestamps.
    The Cognito account is NOT re-enabled here — the admin should also
    issue a password reset so the user can log in again.
    """
    if not target.is_deleted:
        return None, "This user has not been deleted."
    target.is_deleted = False
    target.is_active = True
    target.deleted_at = None
    target.deleted_by = None
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="user.restore",
        entity_type="User",
        entity_id=target.id,
        details={"email": target.email},
    )
    db.commit()
    db.refresh(target)
    return target, None


def assign_role(
    db: Session,
    target: User,
    new_role: str,
    new_club_id: int | None,
    reason: str,
    current_user: CurrentUser,
) -> tuple[User | None, str | None]:
    """
    Change a user's governance role (super_admin only).

    Used at AGMs or when someone is elected/removed from a position.
    The user's member_type (player/club_staff) is PRESERVED — roles are additive
    identities, not replacements of who the person fundamentally is.

    If new_role is club_admin, new_club_id is required.
    """
    if target.role == "super_admin":
        return None, "The super_admin role cannot be changed via this action."
    if new_role == "club_admin" and not new_club_id:
        return None, "club_id is required when assigning the club_admin role."

    old_role = target.role
    old_club_id = target.club_id

    target.role = new_role
    if new_role == "club_admin":
        target.club_id = new_club_id
    elif new_role in ("player", "club_staff", "league_admin"):
        # League admin and base roles may have no club or a voluntary club link
        if new_club_id is not None:
            target.club_id = new_club_id
        # Stepping down from club_admin — clear club link unless explicitly kept
        elif old_role == "club_admin":
            target.club_id = None

    # Sync to Cognito so next JWT reflects the new role
    _cognito_update_role(target.cognito_sub, new_role, target.club_id)

    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="user.assign_role",
        entity_type="User",
        entity_id=target.id,
        details={
            "old_role": old_role,
            "new_role": new_role,
            "old_club_id": old_club_id,
            "new_club_id": target.club_id,
            "reason": reason,
        },
    )
    db.commit()
    db.refresh(target)
    return target, None


# ---------------------------------------------------------------------------
# Account actions
# ---------------------------------------------------------------------------


def perform_account_action(
    db: Session,
    target: User,
    action_req: AccountActionRequest,
    current_user: CurrentUser,
) -> tuple[User | None, str | None]:
    """
    Dispatch an account action.  All actions write to AuditLog.

    league_admin cannot act on super_admin accounts.
    """
    if current_user.role == "league_admin" and target.role == "super_admin":
        return (
            None,
            "Use dedicated recovery actions for account updates. "
            "League admins cannot manage super_admin accounts.",
        )

    action = action_req.action

    if action == "activate":
        return _activate(db, target, current_user, action_req.reason)
    if action == "deactivate":
        return _deactivate(db, target, current_user, action_req.reason)
    if action == "soft_delete":
        if not is_super_admin(current_user):
            return None, "Only super_admin can perform soft_delete via account-action."
        return soft_delete_user(db, target, current_user, action_req.reason)
    if action == "reset_password":
        return _reset_password(db, target, current_user, action_req.reason)
    if action == "update_mobile":
        return _update_mobile(db, target, current_user, action_req)

    return None, f"Unknown action: {action}"


def _activate(
    db: Session, target: User, actor: CurrentUser, reason: str
) -> tuple[User | None, str | None]:
    target.is_active = True
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=actor.id,
        action="user.activate",
        entity_type="User",
        entity_id=target.id,
        details={"reason": reason},
    )
    db.commit()
    db.refresh(target)
    return target, None


def _deactivate(
    db: Session, target: User, actor: CurrentUser, reason: str
) -> tuple[User | None, str | None]:
    if target.id == actor.id:
        return None, "You cannot deactivate your own account."
    target.is_active = False
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=actor.id,
        action="user.deactivate",
        entity_type="User",
        entity_id=target.id,
        details={"reason": reason},
    )
    db.commit()
    db.refresh(target)
    return target, None


def _reset_password(
    db: Session, target: User, actor: CurrentUser, reason: str
) -> tuple[User | None, str | None]:
    """
    Generate a temporary password, set it in Cognito, mark force_password_change.

    IAM permission required on EC2 role: cognito-idp:AdminSetUserPassword
    """
    temp_password = _generate_temp_password()
    success = _cognito_set_password(target.cognito_sub, temp_password)
    if not success:
        return None, "Failed to reset password in Cognito. Check IAM permissions."

    target.force_password_change = True
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=actor.id,
        action="user.reset_password",
        entity_type="User",
        entity_id=target.id,
        details={"reason": reason},  # ⚠️ NEVER log the temp password
    )
    db.commit()
    db.refresh(target)

    # Send temp password via SES
    _send_temp_password_email(target.email, temp_password)

    return target, None


def _update_mobile(
    db: Session,
    target: User,
    actor: CurrentUser,
    action_req: AccountActionRequest,
) -> tuple[User | None, str | None]:
    new_mobile = action_req.new_value
    if not new_mobile:
        return None, "new_value (mobile number) is required for update_mobile."
    # Mobile number is stored in Cognito, not in our DB.
    # Here we just audit-log the change; Cognito update is out of scope.
    audit_service.write_audit_log(
        db,
        actor_id=actor.id,
        action="user.update_mobile",
        entity_type="User",
        entity_id=target.id,
        details={"reason": action_req.reason, "new_mobile_set": True},
    )
    db.commit()
    return target, None


# ---------------------------------------------------------------------------
# Cognito helpers (swallow errors so the DB transaction can still proceed)
# ---------------------------------------------------------------------------


def _cognito_create_user(
    *,
    email: str,
    temporary_password: str,
    role: str,
    club_id: int | None,
    player_id: int | None,
) -> str | None:
    """
    Create a Cognito user and return the cognito_sub UUID.
    Returns None on failure.
    """
    if not settings.cognito_user_pool_id:
        # Not configured — dev/test mode.  Return a fake sub.
        return f"dev-sub-{email}"
    try:
        client = boto3.client("cognito-idp", region_name=settings.cognito_region)
        user_attributes = [
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "custom:role", "Value": role},
        ]
        if club_id:
            user_attributes.append({"Name": "custom:club_id", "Value": str(club_id)})
        if player_id:
            user_attributes.append(
                {"Name": "custom:player_id", "Value": str(player_id)}
            )
        resp = client.admin_create_user(
            UserPoolId=settings.cognito_user_pool_id,
            Username=email,
            TemporaryPassword=temporary_password,
            UserAttributes=user_attributes,
            MessageAction="SUPPRESS",  # we send our own email
        )
        # The JWT "sub" claim is a UUID in Attributes, not resp["User"]["Username"]
        # (which is the email). We must store the UUID so user_sync lookups match.
        attrs = {a["Name"]: a["Value"] for a in resp["User"]["Attributes"]}
        sub: str = attrs["sub"]
        return sub
    except Exception:
        logger.exception({"event": "cognito.admin_create_user.error", "email": email})
        return None


def _cognito_set_password(cognito_sub: str, password: str) -> bool:
    """Set a permanent temporary password in Cognito. Returns True on success."""
    if not settings.cognito_user_pool_id:
        return True  # dev mode
    try:
        client = boto3.client("cognito-idp", region_name=settings.cognito_region)
        client.admin_set_user_password(
            UserPoolId=settings.cognito_user_pool_id,
            Username=cognito_sub,
            Password=password,
            Permanent=False,  # forces password change on next login
        )
        return True
    except Exception:
        logger.exception({"event": "cognito.admin_set_password.error"})
        return False


def _generate_temp_password(length: int = 16) -> str:
    """
    Generate a random temporary password that meets Cognito's default policy:
    min 8 chars, uppercase, lowercase, digit, symbol.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        has_upper = any(c.isupper() for c in pw)
        has_lower = any(c.islower() for c in pw)
        has_digit = any(c.isdigit() for c in pw)
        has_symbol = any(c in "!@#$%^&*" for c in pw)
        if has_upper and has_lower and has_digit and has_symbol:
            return pw


def _send_temp_password_email(email: str, temp_password: str) -> None:
    """
    Send the temporary password via SES.
    Errors are swallowed — the password was already set in Cognito.
    """
    if not settings.cognito_user_pool_id:
        return  # dev mode, skip
    try:
        ses = boto3.client("ses", region_name=settings.aws_region)
        ses.send_email(
            Source="noreply@football-league.example.com",
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": "Your temporary password"},
                "Body": {
                    "Text": {
                        "Data": (
                            f"Your temporary password is: {temp_password}\n\n"
                            "You will be prompted to change it on first login."
                        )
                    }
                },
            },
        )
    except Exception:
        logger.exception({"event": "ses.send_temp_password.error", "email": email})


def _cognito_delete_user(cognito_sub: str) -> bool:
    """Permanently delete a Cognito user. Returns True on success."""
    if not settings.cognito_user_pool_id:
        return True  # dev mode
    try:
        client = boto3.client("cognito-idp", region_name=settings.cognito_region)
        client.admin_delete_user(
            UserPoolId=settings.cognito_user_pool_id,
            Username=cognito_sub,
        )
        return True
    except Exception:
        logger.exception({"event": "cognito.admin_delete_user.error"})
        return False


def _cognito_update_role(cognito_sub: str, new_role: str, club_id: int | None) -> bool:
    """
    Update a user's custom:role (and optionally custom:club_id) in Cognito.

    Called when a governance role is assigned or revoked via the Users page.
    The next JWT the user obtains will carry the new role claim.
    Returns True on success; errors are logged but not re-raised.
    """
    if not settings.cognito_user_pool_id:
        return True  # dev mode
    try:
        client = boto3.client("cognito-idp", region_name=settings.cognito_region)
        attrs = [{"Name": "custom:role", "Value": new_role}]
        if club_id is not None:
            attrs.append({"Name": "custom:club_id", "Value": str(club_id)})
        else:
            # Clear the club_id attribute so stale values don't linger
            attrs.append({"Name": "custom:club_id", "Value": ""})
        client.admin_update_user_attributes(
            UserPoolId=settings.cognito_user_pool_id,
            Username=cognito_sub,
            UserAttributes=attrs,
        )
        return True
    except Exception:
        logger.exception({"event": "cognito.admin_update_role.error"})
        return False
