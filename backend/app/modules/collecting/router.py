"""
Collecting router: video processing API endpoints with database persistence
"""
import uuid
import asyncio
import shutil
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ...core.config import TASKS_DIR, DATABASE_URL
from ...core.database import get_db
from ...core.security import get_current_user, get_current_user_optional
from ...models.user import User
from ...models.collecting import CollectingTask
from .schemas import VideoRequest, TaskResponse, TaskStatus, UserTasksResponse
from .pipeline import VideoPipeline

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory cache for active task progress (for real-time updates)
active_tasks: Dict[str, Dict] = {}

# Track running asyncio tasks for cancellation
running_tasks: Dict[str, asyncio.Task] = {}


def cleanup_stuck_tasks(db: Session, user_id: Optional[int] = None):
    """Mark stuck tasks (pending/processing but not in active_tasks) as cancelled"""
    query = db.query(CollectingTask).filter(
        CollectingTask.status.in_(["pending", "processing"])
    )
    if user_id:
        query = query.filter(CollectingTask.user_id == user_id)
    
    stuck_tasks = query.all()
    
    for task in stuck_tasks:
        # If task is not in active_tasks and has been pending for > 5 minutes, mark as cancelled
        if task.task_id not in active_tasks:
            time_since_created = datetime.utcnow() - task.created_at.replace(tzinfo=None) if task.created_at else timedelta(hours=1)
            if time_since_created > timedelta(minutes=5):
                task.status = "cancelled"
                task.message = "Task was cancelled (server restarted)"
                task.error = "Task was interrupted due to server restart"
                logger.info(f"Marked stuck task {task.task_id[:8]}... as cancelled")
    
    db.commit()


def update_task_progress(task_id: str, percent: int, message: str, db: Session):
    """Callback function to update task progress in memory and database"""
    # Check if task was cancelled
    if task_id in active_tasks and active_tasks[task_id].get("cancelled"):
        raise asyncio.CancelledError("Task was cancelled by user")
    
    # Update in-memory cache
    if task_id in active_tasks:
        active_tasks[task_id]["progress"] = percent
        active_tasks[task_id]["message"] = message
    
    # Update database (periodically)
    if percent % 5 == 0 or percent >= 100:
        try:
            task = db.query(CollectingTask).filter(CollectingTask.task_id == task_id).first()
            if task:
                task.progress = percent
                task.message = message
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to update task progress in DB: {e}")
    
    logger.info(f"Task {task_id[:8]}... [{percent}%] {message}")


async def process_video_task(task_id: str, youtube_url: str, max_videos: int, db_url: str):
    """Background task to process video"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    work_dir = TASKS_DIR / task_id
    
    try:
        # Update status to processing
        task = db.query(CollectingTask).filter(CollectingTask.task_id == task_id).first()
        if task:
            task.status = "processing"
            task.message = "Initializing pipeline..."
            task.started_at = datetime.utcnow()
            task.work_dir = str(work_dir)
            db.commit()
        
        if task_id in active_tasks:
            active_tasks[task_id]["status"] = "processing"
            active_tasks[task_id]["message"] = "Initializing pipeline..."
        
        def progress_callback(percent: int, message: str):
            # Check for cancellation
            if task_id in active_tasks and active_tasks[task_id].get("cancelled"):
                raise Exception("Task cancelled by user")
            update_task_progress(task_id, percent, message, db)
        
        pipeline = VideoPipeline(work_dir, progress_callback=progress_callback)
        
        loop = asyncio.get_event_loop()
        zip_path = await loop.run_in_executor(None, pipeline.run, youtube_url, max_videos)
        
        # Update final status
        task = db.query(CollectingTask).filter(CollectingTask.task_id == task_id).first()
        if task:
            if zip_path and zip_path.exists():
                task.status = "completed"
                task.progress = 100
                task.message = "Processing complete!"
                task.zip_path = str(zip_path)
                task.completed_at = datetime.utcnow()
                logger.info(f"Task {task_id[:8]}... completed successfully")
                
                if task_id in active_tasks:
                    active_tasks[task_id].update({
                        "status": "completed",
                        "progress": 100,
                        "message": "Processing complete!",
                        "zip_path": str(zip_path),
                        "download_url": f"/api/collecting/download/{task_id}"
                    })
            else:
                task.status = "failed"
                task.error = "Pipeline failed to generate output"
                logger.error(f"Task {task_id[:8]}... failed")
                
                if task_id in active_tasks:
                    active_tasks[task_id].update({
                        "status": "failed",
                        "error": "Pipeline failed to generate output"
                    })
            
            db.commit()
    
    except asyncio.CancelledError:
        logger.info(f"Task {task_id[:8]}... was cancelled")
        try:
            task = db.query(CollectingTask).filter(CollectingTask.task_id == task_id).first()
            if task:
                task.status = "cancelled"
                task.message = "Task cancelled by user"
                db.commit()
        except:
            pass
        
        if task_id in active_tasks:
            active_tasks[task_id].update({
                "status": "cancelled",
                "message": "Task cancelled by user"
            })
            
    except Exception as e:
        error_msg = str(e)
        if "cancelled" in error_msg.lower():
            logger.info(f"Task {task_id[:8]}... was cancelled")
            status = "cancelled"
            message = "Task cancelled by user"
        else:
            logger.exception(f"Task {task_id[:8]}... error: {e}")
            status = "failed"
            message = error_msg
        
        try:
            task = db.query(CollectingTask).filter(CollectingTask.task_id == task_id).first()
            if task:
                task.status = status
                task.error = message
                db.commit()
        except:
            pass
        
        if task_id in active_tasks:
            active_tasks[task_id].update({
                "status": status,
                "error": message
            })
    finally:
        db.close()
        # Remove from running tasks
        if task_id in running_tasks:
            del running_tasks[task_id]


@router.post("/process", response_model=TaskResponse)
async def process_video(
    request: VideoRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Start video processing task
    Only one task can run at a time per user
    """
    # Validate URL
    if not request.youtube_url:
        raise HTTPException(status_code=400, detail="YouTube URL is required")
    
    if "youtube.com" not in request.youtube_url and "youtu.be" not in request.youtube_url:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    user_id = current_user.id if current_user else None
    
    # Check if user already has a running task
    if user_id:
        # Clean up stuck tasks first
        cleanup_stuck_tasks(db, user_id)
        
        existing_task = db.query(CollectingTask).filter(
            CollectingTask.user_id == user_id,
            CollectingTask.status.in_(["pending", "processing"])
        ).first()
        
        if existing_task:
            raise HTTPException(
                status_code=400, 
                detail=f"Bạn đã có task đang chạy (ID: {existing_task.task_id[:8]}...). Vui lòng hủy task đó trước khi tạo task mới."
            )
    
    # Create task ID
    task_id = str(uuid.uuid4())
    
    # Save to database
    db_task = CollectingTask(
        task_id=task_id,
        user_id=user_id,
        youtube_url=request.youtube_url,
        max_videos=request.max_videos,
        status="pending",
        progress=0,
        message="Task queued"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    # Add to in-memory cache
    active_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "Task queued",
        "youtube_url": request.youtube_url,
        "max_videos": request.max_videos,
        "created_at": db_task.created_at.isoformat(),
        "user_id": user_id,
        "zip_path": None,
        "error": None,
        "cancelled": False
    }
    
    # Start background task
    background_tasks.add_task(
        process_video_task, 
        task_id, 
        request.youtube_url, 
        request.max_videos,
        DATABASE_URL
    )
    
    logger.info(f"Created task {task_id[:8]}... for URL: {request.youtube_url}, max_videos: {request.max_videos}, user_id: {user_id}")
    
    return TaskResponse(
        task_id=task_id,
        message="Processing started"
    )


@router.post("/cancel/{task_id}")
async def cancel_task(
    task_id: str, 
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Cancel a running task"""
    db_task = db.query(CollectingTask).filter(CollectingTask.task_id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check ownership
    if current_user and db_task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền hủy task này")
    
    if db_task.status not in ["pending", "processing"]:
        raise HTTPException(status_code=400, detail="Task không thể hủy (đã hoàn thành hoặc đã thất bại)")
    
    # Mark as cancelled in memory (will be picked up by progress callback)
    if task_id in active_tasks:
        active_tasks[task_id]["cancelled"] = True
        active_tasks[task_id]["status"] = "cancelled"
        active_tasks[task_id]["message"] = "Đang hủy..."
    
    # Update database
    db_task.status = "cancelled"
    db_task.message = "Task cancelled by user"
    db_task.error = "Cancelled by user"
    db.commit()
    
    # Clean up work directory using rm -rf
    work_dir = TASKS_DIR / task_id
    if work_dir.exists():
        try:
            subprocess.run(['rm', '-rf', str(work_dir)], check=True)
            logger.info(f"Deleted task folder: {work_dir}")
        except subprocess.CalledProcessError:
            shutil.rmtree(work_dir, ignore_errors=True)
    
    logger.info(f"Task {task_id[:8]}... cancelled by user")
    
    return {"message": "Task đã được hủy", "task_id": task_id}


@router.get("/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """Get the status of a processing task"""
    # First check in-memory cache
    if task_id in active_tasks:
        task = active_tasks[task_id]
        return TaskStatus(
            task_id=task_id,
            status=task["status"],
            progress=task["progress"],
            message=task["message"],
            created_at=task["created_at"],
            download_url=f"/api/collecting/download/{task_id}" if task["status"] == "completed" else None,
            error=task.get("error")
        )
    
    # Fall back to database
    db_task = db.query(CollectingTask).filter(CollectingTask.task_id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskStatus(
        task_id=task_id,
        status=db_task.status,
        progress=db_task.progress,
        message=db_task.message or "",
        created_at=db_task.created_at.isoformat() if db_task.created_at else "",
        download_url=f"/api/collecting/download/{task_id}" if db_task.status == "completed" else None,
        error=db_task.error
    )


@router.get("/download/{task_id}")
async def download_result(task_id: str, db: Session = Depends(get_db)):
    """Download the processed ZIP file"""
    zip_path = None
    status = None
    
    if task_id in active_tasks:
        zip_path = active_tasks[task_id].get("zip_path")
        status = active_tasks[task_id].get("status")
    
    if not zip_path:
        db_task = db.query(CollectingTask).filter(CollectingTask.task_id == task_id).first()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
        zip_path = db_task.zip_path
        status = db_task.status
    
    if status != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")
    
    if not zip_path or not Path(zip_path).exists():
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"visl_clips_{task_id[:8]}.zip"
    )


@router.delete("/task/{task_id}")
async def delete_task(task_id: str, db: Session = Depends(get_db)):
    """Delete a task and its files"""
    db_task = db.query(CollectingTask).filter(CollectingTask.task_id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Remove work directory using rm -rf for thorough deletion
    work_dir = TASKS_DIR / task_id
    if work_dir.exists():
        try:
            subprocess.run(['rm', '-rf', str(work_dir)], check=True)
            logger.info(f"Deleted task folder: {work_dir}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to delete folder with rm -rf: {e}, falling back to shutil")
            shutil.rmtree(work_dir, ignore_errors=True)
    
    db.delete(db_task)
    db.commit()
    
    if task_id in active_tasks:
        del active_tasks[task_id]
    
    logger.info(f"Task {task_id[:8]}... deleted from database and storage")
    return {"message": "Task deleted"}


@router.get("/tasks", response_model=List[TaskStatus])
async def list_all_tasks(db: Session = Depends(get_db)):
    """List all tasks (admin only)"""
    db_tasks = db.query(CollectingTask).order_by(CollectingTask.created_at.desc()).limit(100).all()
    
    return [
        TaskStatus(
            task_id=task.task_id,
            status=task.status,
            progress=task.progress,
            message=task.message or "",
            created_at=task.created_at.isoformat() if task.created_at else "",
            download_url=f"/api/collecting/download/{task.task_id}" if task.status == "completed" else None,
            error=task.error
        )
        for task in db_tasks
    ]


@router.get("/my-tasks", response_model=UserTasksResponse)
async def get_my_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all tasks for the current logged-in user"""
    # Clean up stuck tasks first
    cleanup_stuck_tasks(db, current_user.id)
    
    db_tasks = db.query(CollectingTask).filter(
        CollectingTask.user_id == current_user.id
    ).order_by(CollectingTask.created_at.desc()).all()
    
    tasks_list = []
    for task in db_tasks:
        if task.task_id in active_tasks:
            mem_task = active_tasks[task.task_id]
            tasks_list.append(TaskStatus(
                task_id=task.task_id,
                status=mem_task["status"],
                progress=mem_task["progress"],
                message=mem_task["message"],
                created_at=task.created_at.isoformat() if task.created_at else "",
                download_url=f"/api/collecting/download/{task.task_id}" if mem_task["status"] == "completed" else None,
                error=mem_task.get("error")
            ))
        else:
            tasks_list.append(TaskStatus(
                task_id=task.task_id,
                status=task.status,
                progress=task.progress,
                message=task.message or "",
                created_at=task.created_at.isoformat() if task.created_at else "",
                download_url=f"/api/collecting/download/{task.task_id}" if task.status == "completed" else None,
                error=task.error
            ))
    
    # Find currently active task
    active_task = None
    for t in tasks_list:
        if t.status in ["pending", "processing"]:
            active_task = t
            break
    
    return UserTasksResponse(
        tasks=tasks_list,
        active_task=active_task
    )
