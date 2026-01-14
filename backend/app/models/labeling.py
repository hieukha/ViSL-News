"""
Models for labeling module: Video, Segment, Annotation
"""
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(255))  # e.g., "HTV Tin Tức"
    file_path = Column(Text, nullable=False)
    duration_seconds = Column(Numeric)
    broadcast_date = Column(DateTime)
    signer_id = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    segments = relationship("Segment", back_populates="video")


class Segment(Base):
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=True)
    clip_name = Column(String(255), unique=True, index=True)  # tên file clip
    clip_path = Column(Text)  # đường dẫn file clip
    video_source = Column(Text)  # đường dẫn video gốc (signer video)
    segment_id = Column(Integer)  # ID trong video gốc
    start_time = Column(Numeric, nullable=False)  # giây
    end_time = Column(Numeric, nullable=False)
    duration = Column(Numeric)
    asr_text = Column(Text)  # transcript tự động từ ASR
    split = Column(String(20), default="train")  # 'train' | 'val' | 'test'
    status = Column(String(50), default="raw")  # 'raw' | 'in_progress' | 'expert_labeled' | 'reviewed'
    is_last_segment = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="segments")
    annotations = relationship("Annotation", back_populates="segment")


class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=False)
    expert_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Chỉnh sửa của chuyên gia
    final_text = Column(Text)  # câu tiếng Việt chuẩn
    gloss_sequence = Column(Text)  # ví dụ: "TÔI|ĐI|HỌC"
    start_time = Column(Numeric)  # có thể khác start_time ban đầu
    end_time = Column(Numeric)
    
    comment = Column(Text)  # ghi chú của chuyên gia
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    segment = relationship("Segment", back_populates="annotations")
    expert = relationship("User", back_populates="annotations")

