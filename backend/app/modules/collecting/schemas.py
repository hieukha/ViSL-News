"""
Collecting module schemas
"""
from pydantic import BaseModel
from typing import Optional


class VideoRequest(BaseModel):
    youtube_url: str
    max_videos: int = 1  # Số video tối đa sẽ xử lý (mặc định 1)


class TaskResponse(BaseModel):
    task_id: str
    message: str


class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: int
    message: str
    created_at: str
    download_url: Optional[str] = None
    error: Optional[str] = None

