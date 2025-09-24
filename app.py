#!/usr/bin/env python3
"""
SmartShopper Application Entry Point
Starts the FastAPI backend server from the root directory.
"""

import sys
import os
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

# Import and run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    from backend.app.main import app
    from backend.app.config import settings
    
    print(f"Starting SmartShopper API on {settings.HOST}:{settings.PORT}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Database: {settings.DATABASE_NAME}")
    
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )