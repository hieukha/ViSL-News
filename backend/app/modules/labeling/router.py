"""
Labeling router: segment and annotation API endpoints
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from ...core.database import get_db
from ...core.security import get_current_user, get_current_user_required
from ...models.user import User
from ...models.labeling import Segment, Annotation
from .schemas import (
    SegmentCreate, SegmentResponse, SegmentListResponse,
    AnnotationCreate, AnnotationResponse,
    StatsResponse
)

router = APIRouter()


# ============ SEGMENT ENDPOINTS ============
@router.get("/segments", response_model=SegmentListResponse)
def get_segments(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    split: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lấy danh sách segments với phân trang và filter"""
    query = db.query(Segment)
    
    if status:
        query = query.filter(Segment.status == status)
    if split:
        query = query.filter(Segment.split == split)
    if search:
        query = query.filter(
            or_(
                Segment.clip_name.ilike(f"%{search}%"),
                Segment.asr_text.ilike(f"%{search}%")
            )
        )
    
    total = query.count()
    segments = query.order_by(Segment.id).offset((page - 1) * per_page).limit(per_page).all()
    
    # Thêm annotation mới nhất cho mỗi segment
    result = []
    for seg in segments:
        seg_dict = SegmentResponse.model_validate(seg)
        latest_ann = db.query(Annotation).filter(
            Annotation.segment_id == seg.id
        ).order_by(Annotation.created_at.desc()).first()
        if latest_ann:
            seg_dict.latest_annotation = AnnotationResponse.model_validate(latest_ann)
        result.append(seg_dict)
    
    return SegmentListResponse(
        segments=result,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/segments/next")
def get_next_segment(
    status: str = "raw",
    split: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lấy segment tiếp theo cần label"""
    query = db.query(Segment).filter(Segment.status == status)
    if split:
        query = query.filter(Segment.split == split)
    
    segment = query.order_by(Segment.id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Không còn mẫu nào cần label")
    
    return SegmentResponse.model_validate(segment)


@router.get("/segments/{segment_id}", response_model=SegmentResponse)
def get_segment(segment_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin segment theo ID"""
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Không tìm thấy segment")
    
    seg_response = SegmentResponse.model_validate(segment)
    latest_ann = db.query(Annotation).filter(
        Annotation.segment_id == segment.id
    ).order_by(Annotation.created_at.desc()).first()
    if latest_ann:
        seg_response.latest_annotation = AnnotationResponse.model_validate(latest_ann)
    
    return seg_response


@router.patch("/segments/{segment_id}/status")
def update_segment_status(
    segment_id: int,
    new_status: str,
    db: Session = Depends(get_db)
):
    """Cập nhật trạng thái segment"""
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Không tìm thấy segment")
    
    segment.status = new_status
    db.commit()
    return {"message": "Đã cập nhật trạng thái", "status": new_status}


# ============ ANNOTATION ENDPOINTS ============
@router.post("/annotations", response_model=AnnotationResponse)
def create_annotation(
    annotation: AnnotationCreate,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Tạo annotation mới (lưu kết quả căn chỉnh của chuyên gia)"""
    segment = db.query(Segment).filter(Segment.id == annotation.segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Không tìm thấy segment")
    
    expert_id = current_user.id if current_user else None
    
    new_annotation = Annotation(
        segment_id=annotation.segment_id,
        expert_id=expert_id,
        final_text=annotation.final_text,
        gloss_sequence=annotation.gloss_sequence,
        start_time=annotation.start_time,
        end_time=annotation.end_time,
        comment=annotation.comment
    )
    db.add(new_annotation)
    
    # Cập nhật status của segment
    segment.status = "expert_labeled"
    
    db.commit()
    db.refresh(new_annotation)
    return new_annotation


@router.get("/annotations/{segment_id}", response_model=List[AnnotationResponse])
def get_annotations(segment_id: int, db: Session = Depends(get_db)):
    """Lấy tất cả annotations của một segment"""
    annotations = db.query(Annotation).filter(
        Annotation.segment_id == segment_id
    ).order_by(Annotation.created_at.desc()).all()
    return annotations


@router.put("/annotations/{annotation_id}", response_model=AnnotationResponse)
def update_annotation(
    annotation_id: int,
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """Cập nhật annotation"""
    db_annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not db_annotation:
        raise HTTPException(status_code=404, detail="Không tìm thấy annotation")
    
    db_annotation.final_text = annotation.final_text
    db_annotation.gloss_sequence = annotation.gloss_sequence
    db_annotation.start_time = annotation.start_time
    db_annotation.end_time = annotation.end_time
    db_annotation.comment = annotation.comment
    
    db.commit()
    db.refresh(db_annotation)
    return db_annotation


# ============ STATISTICS ENDPOINTS ============
@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Lấy thống kê tổng quan"""
    total = db.query(Segment).count()
    raw = db.query(Segment).filter(Segment.status == "raw").count()
    in_progress = db.query(Segment).filter(Segment.status == "in_progress").count()
    labeled = db.query(Segment).filter(Segment.status == "expert_labeled").count()
    reviewed = db.query(Segment).filter(Segment.status == "reviewed").count()
    
    train = db.query(Segment).filter(Segment.split == "train").count()
    val = db.query(Segment).filter(Segment.split == "val").count()
    test = db.query(Segment).filter(Segment.split == "test").count()
    
    total_annotations = db.query(Annotation).count()
    
    avg_duration = db.query(func.avg(Segment.duration)).scalar()
    
    return StatsResponse(
        total_segments=total,
        raw_count=raw,
        in_progress_count=in_progress,
        labeled_count=labeled,
        reviewed_count=reviewed,
        train_count=train,
        val_count=val,
        test_count=test,
        total_annotations=total_annotations,
        avg_duration=float(avg_duration) if avg_duration else None
    )

