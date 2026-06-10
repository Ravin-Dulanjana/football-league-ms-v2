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
    #   league_admin → league_admin, club_admin, player (not super_admin)
    #   club_admin   → player only
    role = current_user.role
    target_role = data.role
    if role == "league_admin" and target_role == "super_admin":
        return None, "League admins cannot create super_admin accounts."
    if role == "club_admin" and target_role != "player":
        return None, "Club admins can only create player accounts."

    # club_admin role requires a club_id
    if target_role == "club_admin" and not data.club_id:
        return None, "club_id is required when creating a club_admin account."

    # Check email is not already taken
    existing = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()
    if existing:
        return None, "A user with that email already exists."

    # For player accounts, create the Player profile first so we get a player_id.
    player_id: int | None = None
    new_player: Player | None = None
    if target_role == "player":
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
        club_id=data.club_id,
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
        club_id=data.club_id,
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
        details={"email": data.email, "role": data.role, "club_id": data.club_id},
    )
    db.commit()
    db.refresh(user)
    logger.info(
        {
            "event": "user.create.complete",
            "user_id": user.id,
            "role": user.role,
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
