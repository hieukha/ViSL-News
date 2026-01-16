"""
Models for labeling module: Dataset, Video, Segment, Annotation
"""
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class Dataset(Base):
    """Dataset - a collection of segments for labeling"""
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    segments = relationship("Segment", back_populates="dataset")
    creator = relationship("User", backref="created_datasets")


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
    """
    Segment status workflow:
    - raw: chưa gán nhãn
    - expert_labeled: đã gán nhãn, chờ admin review
    - needs_fix: bị admin trả về cần sửa
    - reviewed: đã được admin duyệt
    """
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)
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
    status = Column(String(50), default="raw")  # 'raw' | 'expert_labeled' | 'needs_fix' | 'reviewed'
    review_comment = Column(Text)  # Admin comment when needs_fix
    is_last_segment = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = relationship("Dataset", back_populates="segments")
    video = relationship("Video", back_populates="segments")
    annotations = relationship("Annotation", back_populates="segment", order_by="desc(Annotation.version)")


class Annotation(Base):
    """Annotation with versioning - each save creates a new version"""
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=False)
    expert_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    version = Column(Integer, default=1)  # version number for history tracking
    
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

