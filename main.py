from fastapi import FastAPI

from app.routers import auth, clubs, players, registration_requests, releases, seasons

app = FastAPI(title="Football League MS v2")

app.include_router(auth.router)
app.include_router(clubs.router)
app.include_router(seasons.router)
app.include_router(players.router)
app.include_router(registration_requests.router)
app.include_router(releases.router)
