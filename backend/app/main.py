import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.challenges import router as challenge_router
from app.api.hints import router as hints_router
from app.api.organizer_auth import router as organizer_auth_router
from app.api.organizer_monitoring import router as organizer_monitoring_router
from app.api.workshops import router as workshop_router
from app.api.dev import router as dev_router
from app.api.c1 import router as c1_router
from app.api.c234 import c2_router, c3_router, c4_router

app = FastAPI(title="Swecha AI Security Lab", version="0.2.0")

environment = os.getenv("ENVIRONMENT", "development").lower()

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(challenge_router, prefix="/api/v1")
app.include_router(hints_router, prefix="/api/v1")
app.include_router(organizer_auth_router, prefix='/api/v1')
app.include_router(organizer_monitoring_router, prefix="/api/v1")
app.include_router(workshop_router, prefix="/api/v1")
app.include_router(c1_router, prefix="/api/v1")
app.include_router(c2_router, prefix="/api/v1")
app.include_router(c3_router, prefix="/api/v1")
app.include_router(c4_router, prefix="/api/v1")

if environment == "development":
    app.include_router(dev_router, prefix="/api/v1")
