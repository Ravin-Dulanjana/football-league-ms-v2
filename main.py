from fastapi import FastAPI

from app.routers import clubs

app = FastAPI(title="Football League MS v2")

app.include_router(clubs.router)
