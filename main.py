from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.middleware.logging import LoggingMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.rate_limit import limiter
from app.routers import (
    audit_logs,
    auth,
    club_memberships,
    club_season_profiles,
    club_staff,
    club_unlock_requests,
    clubs,
    league_info,
    notifications,
    players,
    registration_requests,
    releases,
    reports,
    seasons,
    users,
)

app = FastAPI(title="Football League MS v2")

# slowapi — attach the limiter so @limiter.limit decorators can find it.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Middleware is applied in reverse order of addition in Starlette.
# RequestIdMiddleware is added SECOND so it becomes the outermost layer
# and runs first — it sets request_id_var before LoggingMiddleware reads it.
#
# CORSMiddleware must be outermost so it handles OPTIONS preflights before
# auth middleware rejects unauthenticated requests. It is added LAST so it
# wraps everything.
#
# Request flow: CORSMiddleware → RequestIdMiddleware → LoggingMiddleware → route handler
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    # allow_credentials=True is required because the Next.js BFF sends the
    # httpOnly id-token cookie on cross-origin requests to this API.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 1-6 routers
app.include_router(auth.router)
app.include_router(clubs.router)
app.include_router(seasons.router)
app.include_router(players.router)
app.include_router(registration_requests.router)
app.include_router(releases.router)
app.include_router(club_memberships.router)

# Phase 8 routers
app.include_router(users.router)
app.include_router(club_season_profiles.router)
app.include_router(club_staff.router)
app.include_router(club_unlock_requests.router)
app.include_router(notifications.router)
app.include_router(audit_logs.router)
app.include_router(reports.router)
app.include_router(league_info.router)
