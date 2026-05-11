import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import admin, analyze, cases

load_dotenv()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Near-Miss Prevention AI API",
        version="0.1.0",
        description="Mock API skeleton for the near-miss prevention system.",
    )

    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(analyze.router)
    app.include_router(cases.router)
    app.include_router(admin.router)

    return app


app = create_app()
