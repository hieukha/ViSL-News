"""
Configuration settings for ViSL Tool
"""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR.parent / "data"
TASKS_DIR = BASE_DIR / "tasks"

# Ensure directories exist
TASKS_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/visl_tool"
)

# Auth settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-visl-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Video settings
VIDEO_DIR = os.getenv("VIDEO_DIR", str(DATA_DIR / "sentence_clips"))
SIGNER_CLIPS_DIR = os.getenv("SIGNER_CLIPS_DIR", str(DATA_DIR / "signer_clips"))

# Hugging Face cache
HF_HOME = os.getenv("HF_HOME", str(BASE_DIR.parent / "cache"))
os.environ['HF_HOME'] = HF_HOME

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

