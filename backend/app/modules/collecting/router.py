"""
Collecting router: video processing API endpoints
"""
import uuid
import asyncio
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from fastapi.responses import FileResponse

from ...core.config import TASKS_DIR
from ...core.security import get_current_user
from ...models.user import User
from .schemas import VideoRequest, TaskResponse, TaskStatus
from .pipeline import VideoPipeline

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory task storage (use Redis in production)
tasks: Dict[str, Dict] = {}


def update_task_progress(task_id: str, percent: int, message: str):
    """Callback function to update task progress"""
    if task_id in tasks:
        tasks[task_id]["progress"] = percent
        tasks[task_id]["message"] = message
        logger.info(f"Task {task_id[:8]}... [{percent}%] {message}")


async def process_video_task(task_id: str, youtube_url: str, max_videos: int = 1, user_id: Optional[int] = None):
    """Background task to process video"""
    work_dir = TASKS_DIR / task_id
    
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["message"] = "Initializing pipeline..."
        
        # Create progress callback
        def progress_callback(percent: int, message: str):
            update_task_progress(task_id, percent, message)
        
        # Run pipeline
        pipeline = VideoPipeline(work_dir, progress_callback=progress_callback)
        
        # Run in executor to not block event loop
        loop = asyncio.get_event_loop()
        zip_path = await loop.run_in_executor(None, pipeline.run, youtube_url, max_videos)
        
        if zip_path and zip_path.exists():
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["message"] = "Processing complete!"
            tasks[task_id]["zip_path"] = str(zip_path)
            tasks[task_id]["download_url"] = f"/api/collecting/download/{task_id}"
            logger.info(f"Task {task_id[:8]}... completed successfully")
        else:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = "Pipeline failed to generate output"
            logger.error(f"Task {task_id[:8]}... failed")
            
    except Exception as e:
        logger.exception(f"Task {task_id[:8]}... error: {e}")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)


@router.post("/process", response_model=TaskResponse)
async def process_video(
    request: VideoRequest, 
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Start video processing task
    
    - **youtube_url**: YouTube video URL to process
    - **max_videos**: Maximum videos to process (for playlists)
    """
    # Validate URL
    if not request.youtube_url:
        raise HTTPException(status_code=400, detail="YouTube URL is required")
    
    if "youtube.com" not in request.youtube_url and "youtu.be" not in request.youtube_url:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    # Create task
    task_id = str(uuid.uuid4())
    user_id = current_user.id if current_user else None
    
    tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "Task queued",
        "youtube_url": request.youtube_url,
        "max_videos": request.max_videos,
        "created_at": datetime.now().isoformat(),
        "user_id": user_id,
        "zip_path": None,
        "error": None
    }
    
    # Start background task
    background_tasks.add_task(
        process_video_task, 
        task_id, 
        request.youtube_url, 
        request.max_videos,
        user_id
    )
    
    logger.info(f"Created task {task_id[:8]}... for URL: {request.youtube_url}, max_videos: {request.max_videos}")
    
    return TaskResponse(
        task_id=task_id,
        message="Processing started"
    )


@router.get("/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get the status of a processing task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    
    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        message=task["message"],
        created_at=task["created_at"],
        download_url=task.get("download_url"),
        error=task.get("error")
    )


@router.get("/download/{task_id}")
async def download_result(task_id: str):
    """Download the processed ZIP file"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")
    
    zip_path = task.get("zip_path")
    if not zip_path or not Path(zip_path).exists():
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"visl_clips_{task_id[:8]}.zip"
    )


@router.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task and its files"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Remove work directory
    work_dir = TASKS_DIR / task_id
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
    
    # Remove from tasks dict
    del tasks[task_id]
    
    return {"message": "Task deleted"}


@router.get("/tasks")
async def list_tasks():
    """List all tasks (for debugging)"""
    return {
        task_id: {
            "status": task["status"],
            "progress": task["progress"],
            "created_at": task["created_at"],
            "user_id": task.get("user_id")
        }
        for task_id, task in tasks.items()
    }

