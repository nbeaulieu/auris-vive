"""
src.api — FastAPI application

    from src.api import create_app
    app = create_app()          # test instantiation
    uvicorn src.api.main:app    # production entry point
"""

from src.api.main import create_app

__all__ = ["create_app"]
