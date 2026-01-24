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
    signer_id: Optional[int] = None  # ID của người ký (từ face clustering)
    split: str = "train"
    status: str = "raw"
    review_comment: Optional[str] = None  # Admin feedback when needs_fix


class SegmentCreate(SegmentBase):
    video_id: Optional[int] = None
    dataset_id: Optional[int] = None


class SegmentResponse(SegmentBase):
    id: int
    dataset_id: Optional[int] = None
    video_id: Optional[int] = None
    is_last_segment: bool = False
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
    expert_name: Optional[str] = None  # Tên người gán nhãn
    version: int = 1  # Version number for history tracking
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ Statistics Schemas ============
class StatsResponse(BaseModel):
    total_segments: int
    raw_count: int
    in_progress_count: int = 0  # Deprecated
    labeled_count: int  # expert_labeled
    needs_fix_count: int = 0  # needs_fix
    reviewed_count: int
    train_count: int
    val_count: int
    test_count: int
    total_annotations: int
    avg_duration: Optional[float] = None


# Update forward references
SegmentResponse.model_rebuild()

