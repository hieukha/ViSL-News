"""
Labeling module schemas
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ============ Segment Schemas ============
class SegmentBase(BaseModel):
    clip_name: str
    clip_path: Optional[str] = None
    video_source: Optional[str] = None
    segment_id: Optional[int] = None
    start_time: float
    end_time: float
    duration: Optional[float] = None
    asr_text: Optional[str] = None
    split: str = "train"
    status: str = "raw"


class SegmentCreate(SegmentBase):
    video_id: Optional[int] = None


class SegmentResponse(SegmentBase):
    id: int
    video_id: Optional[int] = None
    created_at: datetime
    latest_annotation: Optional["AnnotationResponse"] = None

    class Config:
        from_attributes = True


class SegmentListResponse(BaseModel):
    segments: List[SegmentResponse]
    total: int
    page: int
    per_page: int


# ============ Annotation Schemas ============
class AnnotationBase(BaseModel):
    final_text: Optional[str] = None
    gloss_sequence: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    comment: Optional[str] = None


class AnnotationCreate(AnnotationBase):
    segment_id: int


class AnnotationResponse(AnnotationBase):
    id: int
    segment_id: int
    expert_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ Statistics Schemas ============
class StatsResponse(BaseModel):
    total_segments: int
    raw_count: int
    in_progress_count: int
    labeled_count: int
    reviewed_count: int
    train_count: int
    val_count: int
    test_count: int
    total_annotations: int
    avg_duration: Optional[float] = None


# Update forward references
SegmentResponse.model_rebuild()

