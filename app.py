"""
Entry point for running uvicorn directly:
uvicorn app:app --reload
"""
from app.main import app

if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
