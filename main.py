from fastapi import FastAPI

from app.middleware.logging import LoggingMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.routers import auth, clubs, players, registration_requests, releases, seasons

app = FastAPI(title="Football League MS v2")

# Middleware is applied in reverse order of addition in Starlette.
# RequestIdMiddleware is added SECOND so it becomes the outermost layer
# and runs first — it sets request_id_var before LoggingMiddleware reads it.
#
# Request flow: RequestIdMiddleware → LoggingMiddleware → route handler
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIdMiddleware)

app.include_router(auth.router)
app.include_router(clubs.router)
app.include_router(seasons.router)
app.include_router(players.router)
app.include_router(registration_requests.router)
app.include_router(releases.router)
