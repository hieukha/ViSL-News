"""
Models for collecting module: CollectingTask
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class CollectingTask(Base):
    """Store video collecting task information for persistence"""
    __tablename__ = "collecting_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Task configuration
    youtube_url = Column(Text, nullable=False)
    max_videos = Column(Integer, default=1)
    
    # Task status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    message = Column(Text, default="Task queued")
    error = Column(Text, nullable=True)
    
    # Output paths
    work_dir = Column(Text, nullable=True)
    zip_path = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship
    user = relationship("User", backref="collecting_tasks")

