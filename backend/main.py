import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import action_image, admin, analyze, cases

load_dotenv()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Near-Miss Prevention AI API",
        version="0.1.0",
        description="Mock API skeleton for the near-miss prevention system.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health")
    def api_health() -> dict[str, object]:
        return {
            "status": "ok",
            "llm_provider": os.getenv("LLM_PROVIDER", "openai"),
            "llm_model_configured": bool(os.getenv("LLM_MODEL")),
            "openai_key_configured": bool(os.getenv("OPENAI_API_KEY")),
            "image_model_configured": bool(os.getenv("OPENAI_IMAGE_MODEL")),
            "database_url_configured": bool(os.getenv("DATABASE_URL")),
        }

    app.include_router(analyze.router)
    app.include_router(action_image.router)
    app.include_router(cases.router)
    app.include_router(admin.router)
    app.include_router(admin.dev_router)

    return app


app = create_app()
