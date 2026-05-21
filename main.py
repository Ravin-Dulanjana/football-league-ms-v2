from fastapi import FastAPI

from app.routers import leagues

app = FastAPI(title="Football League MS v2")

app.include_router(leagues.router)
