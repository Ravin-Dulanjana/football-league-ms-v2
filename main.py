from fastapi import FastAPI

from app.middleware.logging import LoggingMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.routers import (
    audit_logs,
    auth,
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

# Middleware is applied in reverse order of addition in Starlette.
# RequestIdMiddleware is added SECOND so it becomes the outermost layer
# and runs first — it sets request_id_var before LoggingMiddleware reads it.
#
# Request flow: RequestIdMiddleware → LoggingMiddleware → route handler
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIdMiddleware)

# Phase 1-6 routers
app.include_router(auth.router)
app.include_router(clubs.router)
app.include_router(seasons.router)
app.include_router(players.router)
app.include_router(registration_requests.router)
app.include_router(releases.router)

# Phase 8 routers
app.include_router(users.router)
app.include_router(club_season_profiles.router)
app.include_router(club_staff.router)
app.include_router(club_unlock_requests.router)
app.include_router(notifications.router)
app.include_router(audit_logs.router)
app.include_router(reports.router)
app.include_router(league_info.router)
