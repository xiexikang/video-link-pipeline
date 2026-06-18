"""FastAPI entry point for the local VLP web console."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.api.routes import artifacts, config_route, doctor, health, jobs

app = FastAPI(
    title="VLP Web API",
    description="Local web API for video-link-pipeline",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5550",
        "http://localhost:5550",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(config_route.router)
app.include_router(doctor.router)
app.include_router(jobs.router)
app.include_router(artifacts.router)
