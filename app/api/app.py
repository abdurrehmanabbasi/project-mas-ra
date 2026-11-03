"""FastAPI application factory for the Autonomous AI Research Assistant."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Autonomous AI Research & Literature Review Assistant",
        description="Multi-agent literature review engine with citation verification and human-in-the-loop review.",
        version="1.0.0",
    )

    # Configure CORS for local development and Streamlit frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.get("/health")
    def health_check():
        return {"status": "healthy", "env": settings.APP_ENV}

    return app


app = create_app()

