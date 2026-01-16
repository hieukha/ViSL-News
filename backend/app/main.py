"""
ViSL Tool - Main FastAPI Application
Combines all modules: auth, collecting, labeling
"""
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import CORS_ORIGINS, VIDEO_DIR, SIGNER_CLIPS_DIR
from .core.database import engine, Base
from .models import User, Video, Segment, Annotation, CollectingTask

# Import routers
from .modules.auth import router as auth_router
from .modules.collecting import router as collecting_router
from .modules.labeling import router as labeling_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("ViSL Tool starting up...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
    yield
    
    logger.info("ViSL Tool shutting down...")


# Create FastAPI app
app = FastAPI(
    title="ViSL Tool API",
    description="""
    Vietnamese Sign Language Tool - Unified API
    
    ## Modules:
    - **Auth**: User authentication (register, login, JWT)
    - **Collecting**: Video processing (download, crop, transcribe, split)
    - **Labeling**: Segment annotation and management
    """,
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for videos
if os.path.exists(VIDEO_DIR):
    app.mount("/videos", StaticFiles(directory=VIDEO_DIR), name="videos")
    logger.info(f"Mounted video directory: {VIDEO_DIR}")

if os.path.exists(SIGNER_CLIPS_DIR):
    app.mount("/signer-videos", StaticFiles(directory=SIGNER_CLIPS_DIR), name="signer_videos")
    logger.info(f"Mounted signer clips directory: {SIGNER_CLIPS_DIR}")

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(collecting_router, prefix="/api/collecting", tags=["Collecting"])
app.include_router(labeling_router, prefix="/api/labeling", tags=["Labeling"])


# ============ HEALTH CHECK ============
@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "ViSL Tool API is running",
        "version": "2.0.0"
    }


@app.get("/")
def root():
    """Root endpoint - API info"""
    return {
        "name": "ViSL Tool API",
        "version": "2.0.0",
        "docs": "/docs",
        "modules": ["auth", "collecting", "labeling"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

