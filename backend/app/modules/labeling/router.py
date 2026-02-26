"""
Labeling router: segment and annotation API endpoints with role-based access
"""
import os
import csv
import shutil
import zipfile
import tempfile
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import subprocess
from sqlalchemy import func, or_
from pydantic import BaseModel

from ...core.database import get_db
from ...core.config import VIDEO_DIR, SIGNER_CLIPS_DIR, DATA_DIR
from ...core.security import get_current_user, get_current_user_required
from ...models.user import User
from ...models.labeling import Dataset, Segment, Annotation, Video
from .schemas import (
    SegmentCreate, SegmentResponse, SegmentListResponse,
    AnnotationCreate, AnnotationResponse,
    StatsResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Ensure data directories exist
Path(VIDEO_DIR).mkdir(parents=True, exist_ok=True)
Path(SIGNER_CLIPS_DIR).mkdir(parents=True, exist_ok=True)


# ============ ROLE-BASED ACCESS HELPERS ============
def require_admin(current_user: User = Depends(get_current_user_required)) -> User:
    """Require user to be admin"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền thực hiện")
    return current_user


def require_annotator_or_admin(current_user: User = Depends(get_current_user_required)) -> User:
    """Require user to be annotator or admin"""
    if current_user.role not in ["admin", "annotator"]:
        raise HTTPException(status_code=403, detail="Bạn không có quyền thực hiện")
    return current_user


# ============ DATASET ENDPOINTS ============
class DatasetCreate(BaseModel):
    name: str
    description: Optional[str] = None


class DatasetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_by: Optional[int]
    created_at: Optional[datetime]
    segment_count: int = 0
    raw_count: int = 0
    labeled_count: int = 0
    needs_fix_count: int = 0
    reviewed_count: int = 0

    class Config:
        from_attributes = True


@router.get("/datasets", response_model=List[DatasetResponse])
def get_datasets(db: Session = Depends(get_db)):
    """Lấy danh sách tất cả datasets"""
    datasets = db.query(Dataset).order_by(Dataset.created_at.desc()).all()
    
    result = []
    for ds in datasets:
        segment_count = db.query(Segment).filter(Segment.dataset_id == ds.id).count()
        raw_count = db.query(Segment).filter(Segment.dataset_id == ds.id, Segment.status == "raw").count()
        labeled_count = db.query(Segment).filter(Segment.dataset_id == ds.id, Segment.status == "expert_labeled").count()
        needs_fix_count = db.query(Segment).filter(Segment.dataset_id == ds.id, Segment.status == "needs_fix").count()
        reviewed_count = db.query(Segment).filter(Segment.dataset_id == ds.id, Segment.status == "reviewed").count()
        
        result.append(DatasetResponse(
            id=ds.id,
            name=ds.name,
            description=ds.description,
            created_by=ds.created_by,
            created_at=ds.created_at,
            segment_count=segment_count,
            raw_count=raw_count,
            labeled_count=labeled_count,
            needs_fix_count=needs_fix_count,
            reviewed_count=reviewed_count
        ))
    
    return result


@router.post("/datasets", response_model=DatasetResponse)
def create_dataset(
    dataset: DatasetCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Tạo dataset mới (Admin only)"""
    existing = db.query(Dataset).filter(Dataset.name == dataset.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Dataset với tên này đã tồn tại")
    
    new_dataset = Dataset(
        name=dataset.name,
        description=dataset.description,
        created_by=current_user.id
    )
    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)
    
    return DatasetResponse(
        id=new_dataset.id,
        name=new_dataset.name,
        description=new_dataset.description,
        created_by=new_dataset.created_by,
        created_at=new_dataset.created_at,
        segment_count=0,
        raw_count=0,
        labeled_count=0,
        needs_fix_count=0,
        reviewed_count=0
    )


@router.delete("/datasets/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    delete_files: bool = Query(False, description="Xóa cả video files"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Xóa dataset và toàn bộ dữ liệu liên quan (Admin only).
    - Xóa tất cả annotations của các segments trong dataset
    - Xóa tất cả segments trong dataset
    - Nếu delete_files=true: xóa cả video files trên disk
    - Xóa dataset
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Không tìm thấy dataset")
    
    dataset_name = dataset.name
    
    # Get all segments in this dataset
    segments = db.query(Segment).filter(Segment.dataset_id == dataset_id).all()
    segment_count = len(segments)
    annotation_count = 0
    files_deleted = 0
    signer_videos_deleted = set()  # Track unique signer videos
    
    try:
        for segment in segments:
            # Delete all annotations for this segment
            ann_deleted = db.query(Annotation).filter(Annotation.segment_id == segment.id).delete()
            annotation_count += ann_deleted
            
            # Delete video files if requested
            if delete_files:
                # Delete sentence clip
                clip_path = Path(VIDEO_DIR) / f"{segment.clip_name}.mp4"
                if clip_path.exists():
                    clip_path.unlink()
                    files_deleted += 1
                    logger.info(f"Deleted clip: {clip_path}")
                
                # Track signer video to delete later (avoid duplicate deletion)
                if segment.video_source:
                    signer_videos_deleted.add(segment.video_source)
        
        # Delete signer videos (only once per unique video)
        if delete_files:
            for signer_name in signer_videos_deleted:
                signer_path = Path(SIGNER_CLIPS_DIR) / signer_name
                if signer_path.exists():
                    signer_path.unlink()
                    logger.info(f"Deleted signer video: {signer_path}")
        
        # Delete all segments
        db.query(Segment).filter(Segment.dataset_id == dataset_id).delete()
        
        # Delete dataset
        db.delete(dataset)
        db.commit()
        
        # Reset segment ID sequence if no segments remain
        remaining_segments = db.query(Segment).count()
        sequence_reset = False
        if remaining_segments == 0:
            from sqlalchemy import text
            db.execute(text("ALTER SEQUENCE segments_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE annotations_id_seq RESTART WITH 1"))
            db.commit()
            sequence_reset = True
            logger.info("Reset segment and annotation ID sequences to 1")
        
        logger.info(f"Deleted dataset '{dataset_name}': {segment_count} segments, {annotation_count} annotations, {files_deleted} files")
        
        return {
            "message": "Đã xóa dataset thành công",
            "dataset_name": dataset_name,
            "segments_deleted": segment_count,
            "annotations_deleted": annotation_count,
            "files_deleted": files_deleted,
            "signer_videos_deleted": len(signer_videos_deleted) if delete_files else 0,
            "sequence_reset": sequence_reset
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting dataset: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa dataset: {str(e)}")


# ============ SEGMENT ENDPOINTS ============
@router.get("/segments", response_model=SegmentListResponse)
def get_segments(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    split: Optional[str] = None,
    search: Optional[str] = None,
    dataset_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Lấy danh sách segments với phân trang và filter"""
    query = db.query(Segment)
    
    if dataset_id:
        query = query.filter(Segment.dataset_id == dataset_id)
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
        ).order_by(Annotation.version.desc()).first()
        if latest_ann:
            ann_response = AnnotationResponse.model_validate(latest_ann)
            if latest_ann.expert:
                ann_response.expert_name = latest_ann.expert.full_name or latest_ann.expert.email
            seg_dict.latest_annotation = ann_response
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
    dataset_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Lấy segment tiếp theo cần label"""
    query = db.query(Segment).filter(Segment.status == status)
    if split:
        query = query.filter(Segment.split == split)
    if dataset_id:
        query = query.filter(Segment.dataset_id == dataset_id)
    
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
    ).order_by(Annotation.version.desc()).first()
    if latest_ann:
        ann_response = AnnotationResponse.model_validate(latest_ann)
        if latest_ann.expert:
            ann_response.expert_name = latest_ann.expert.full_name or latest_ann.expert.email
        seg_response.latest_annotation = ann_response
    
    return seg_response


# ============ ADMIN REVIEW ENDPOINTS ============
class ReviewRequest(BaseModel):
    comment: Optional[str] = None


@router.post("/segments/{segment_id}/review/approve")
def approve_segment(
    segment_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin đánh dấu segment đạt yêu cầu (reviewed)"""
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Không tìm thấy segment")
    
    if segment.status != "expert_labeled":
        raise HTTPException(status_code=400, detail="Chỉ có thể duyệt segment đã được gán nhãn")
    
    segment.status = "reviewed"
    segment.review_comment = None
    db.commit()
    
    logger.info(f"Admin {current_user.email} approved segment {segment_id}")
    return {"message": "Đã duyệt segment", "status": "reviewed"}


@router.post("/segments/{segment_id}/review/reject")
def reject_segment(
    segment_id: int,
    review: ReviewRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin trả về segment cần sửa (needs_fix)"""
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Không tìm thấy segment")
    
    if segment.status != "expert_labeled":
        raise HTTPException(status_code=400, detail="Chỉ có thể từ chối segment đã được gán nhãn")
    
    segment.status = "needs_fix"
    segment.review_comment = review.comment
    db.commit()
    
    logger.info(f"Admin {current_user.email} rejected segment {segment_id}")
    return {"message": "Đã trả về để sửa", "status": "needs_fix"}


# ============ ANNOTATION ENDPOINTS ============
@router.post("/annotations", response_model=AnnotationResponse)
def create_annotation(
    annotation: AnnotationCreate,
    current_user: User = Depends(require_annotator_or_admin),
    db: Session = Depends(get_db)
):
    """
    Tạo annotation mới (lưu kết quả căn chỉnh).
    - Mỗi lần lưu tạo 1 version mới
    - Sau khi lưu, status luôn chuyển về expert_labeled
    - Admin không có quyền tạo annotation
    """
    # Admin không được tạo annotation
    if current_user.role == "admin":
        raise HTTPException(status_code=403, detail="Admin không có quyền gán nhãn, chỉ có quyền duyệt")
    
    segment = db.query(Segment).filter(Segment.id == annotation.segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Không tìm thấy segment")
    
    # Get next version number
    max_version = db.query(func.max(Annotation.version)).filter(
        Annotation.segment_id == annotation.segment_id
    ).scalar() or 0
    
    new_annotation = Annotation(
        segment_id=annotation.segment_id,
        expert_id=current_user.id,
        version=max_version + 1,
        final_text=annotation.final_text,
        gloss_sequence=annotation.gloss_sequence,
        start_time=annotation.start_time,
        end_time=annotation.end_time,
        comment=annotation.comment
    )
    db.add(new_annotation)
    
    # Cập nhật status của segment luôn về expert_labeled (chờ admin review)
    segment.status = "expert_labeled"
    segment.review_comment = None  # Clear review comment
    
    db.commit()
    db.refresh(new_annotation)
    
    logger.info(f"Annotator {current_user.email} created annotation v{new_annotation.version} for segment {segment.id}")
    return new_annotation


@router.get("/annotations/{segment_id}", response_model=List[AnnotationResponse])
def get_annotations(segment_id: int, db: Session = Depends(get_db)):
    """Lấy tất cả annotations (history) của một segment với thông tin người gán nhãn"""
    annotations = db.query(Annotation).filter(
        Annotation.segment_id == segment_id
    ).order_by(Annotation.version.desc()).all()
    
    result = []
    for ann in annotations:
        ann_dict = AnnotationResponse.model_validate(ann)
        # Thêm tên người gán nhãn
        if ann.expert:
            ann_dict.expert_name = ann.expert.full_name or ann.expert.email
        result.append(ann_dict)
    
    return result


# ============ STATISTICS ENDPOINTS ============
@router.get("/stats", response_model=StatsResponse)
def get_stats(
    dataset_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Lấy thống kê tổng quan"""
    query = db.query(Segment)
    if dataset_id:
        query = query.filter(Segment.dataset_id == dataset_id)
    
    total = query.count()
    raw = query.filter(Segment.status == "raw").count()
    labeled = query.filter(Segment.status == "expert_labeled").count()
    needs_fix = query.filter(Segment.status == "needs_fix").count()
    reviewed = query.filter(Segment.status == "reviewed").count()
    
    train = query.filter(Segment.split == "train").count()
    val = query.filter(Segment.split == "val").count()
    test = query.filter(Segment.split == "test").count()
    
    if dataset_id:
        total_annotations = db.query(Annotation).join(Segment).filter(
            Segment.dataset_id == dataset_id
        ).count()
        avg_duration = db.query(func.avg(Segment.duration)).filter(
            Segment.dataset_id == dataset_id
        ).scalar()
    else:
        total_annotations = db.query(Annotation).count()
        avg_duration = db.query(func.avg(Segment.duration)).scalar()
    
    return StatsResponse(
        total_segments=total,
        raw_count=raw,
        in_progress_count=0,  # Deprecated, use needs_fix_count instead
        labeled_count=labeled,
        reviewed_count=reviewed,
        needs_fix_count=needs_fix,
        train_count=train,
        val_count=val,
        test_count=test,
        total_annotations=total_annotations,
        avg_duration=float(avg_duration) if avg_duration else None
    )


# ============ UPLOAD ZIP ENDPOINT (Admin only) ============
@router.post("/upload-zip")
async def upload_zip(
    file: UploadFile = File(...),
    dataset_name: str = Query(..., description="Tên dataset"),
    split: str = Query("train", description="Split: train, val, test"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Upload ZIP file từ collecting để import vào labeling (Admin only).
    Tự động tạo dataset mới nếu chưa tồn tại.
    ZIP cần có:
    - sentence_clips/ folder chứa video clips
    - signer_clips/ folder chứa signer videos (video gốc có người ký)
    - sentence_clips_metadata.csv file chứa metadata
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file ZIP")
    
    # Get or create dataset
    dataset = db.query(Dataset).filter(Dataset.name == dataset_name).first()
    if not dataset:
        dataset = Dataset(
            name=dataset_name,
            description=f"Imported from {file.filename}",
            created_by=current_user.id
        )
        db.add(dataset)
        db.flush()  # Get ID without committing
        logger.info(f"Created new dataset: {dataset_name}")
    
    # Create temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / file.filename
        
        # Save uploaded file
        logger.info(f"Saving uploaded file: {file.filename}")
        with open(zip_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Extract ZIP
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(temp_path)
            logger.info(f"Extracted ZIP to {temp_path}")
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="File ZIP không hợp lệ")
        
        # Find metadata CSV
        csv_path = temp_path / "sentence_clips_metadata.csv"
        if not csv_path.exists():
            raise HTTPException(
                status_code=400, 
                detail="Không tìm thấy file sentence_clips_metadata.csv trong ZIP"
            )
        
        # Find sentence_clips folder
        clips_folder = temp_path / "sentence_clips"
        if not clips_folder.exists():
            raise HTTPException(
                status_code=400,
                detail="Không tìm thấy folder sentence_clips trong ZIP"
            )
        
        # Find signer_clips folder (optional but recommended)
        signer_folder = temp_path / "signer_clips"
        signer_videos_copied = 0
        
        # Copy signer videos first (if exists)
        if signer_folder.exists():
            logger.info(f"Found signer_clips folder, copying signer videos...")
            for signer_file in signer_folder.glob("*.mp4"):
                dest_signer = Path(SIGNER_CLIPS_DIR) / signer_file.name
                if not dest_signer.exists():
                    shutil.copy2(signer_file, dest_signer)
                    signer_videos_copied += 1
                    logger.info(f"Copied signer video: {signer_file.name}")
        else:
            logger.warning("No signer_clips folder found in ZIP - labeling may not show full videos")
        
        # Read CSV and import data
        imported_count = 0
        skipped_count = 0
        errors = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    clip_name = row.get('name', '')
                    if not clip_name:
                        continue
                    
                    # Check if clip already exists
                    existing = db.query(Segment).filter(Segment.clip_name == clip_name).first()
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Find video file
                    video_file = clips_folder / f"{clip_name}.mp4"
                    if not video_file.exists():
                        errors.append(f"Video không tồn tại: {clip_name}.mp4")
                        continue
                    
                    # Copy sentence clip to data directory
                    dest_path = Path(VIDEO_DIR) / f"{clip_name}.mp4"
                    shutil.copy2(video_file, dest_path)
                    
                    # Parse times - use original timestamps from transcript
                    # (start_original/end_original are the actual speech boundaries)
                    try:
                        # Prefer original timestamps, fallback to rounded if not available
                        start_time = float(row.get('start_original', row.get('start_rounded', 0)))
                        end_time = float(row.get('end_original', row.get('end_rounded', 0)))
                        duration = float(row.get('duration', 0))
                    except (ValueError, TypeError):
                        start_time = 0
                        end_time = 0
                        duration = 0
                    
                    # Parse signer_id from CSV (from face clustering)
                    signer_id = None
                    if row.get('signer_id'):
                        try:
                            signer_id = int(row.get('signer_id'))
                        except (ValueError, TypeError):
                            signer_id = None
                    
                    # Create segment record
                    segment = Segment(
                        dataset_id=dataset.id,
                        clip_name=clip_name,
                        clip_path=str(dest_path),
                        video_source=row.get('video_source', ''),
                        segment_id=int(row.get('segment_id', 0)) if row.get('segment_id') else None,
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        asr_text=row.get('text', ''),
                        signer_id=signer_id,
                        split=split,
                        status='raw',
                        is_last_segment=row.get('is_last_segment', '').lower() == 'true'
                    )
                    
                    db.add(segment)
                    imported_count += 1
                
                db.commit()
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error importing data: {e}")
            raise HTTPException(status_code=500, detail=f"Lỗi import dữ liệu: {str(e)}")
        
        logger.info(f"Import completed: {imported_count} segments, {signer_videos_copied} signer videos to dataset '{dataset_name}'")
        
        return {
            "message": "Import thành công",
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "imported": imported_count,
            "skipped": skipped_count,
            "signer_videos": signer_videos_copied,
            "errors": errors[:10] if errors else []
        }


# ============ EXPORT DATASET ============

def cut_video_clip(input_path: Path, output_path: Path, start_time: float, end_time: float) -> bool:
    """Cut a video clip using ffmpeg with precise timestamps"""
    duration = end_time - start_time
    if duration <= 0:
        return False
    
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-i', str(input_path),
        '-t', str(duration),
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-avoid_negative_ts', 'make_zero',
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode == 0 and output_path.exists()
    except Exception as e:
        logger.error(f"Error cutting video: {e}")
        return False


@router.get("/datasets/{dataset_id}/export")
async def export_dataset(
    dataset_id: int,
    include_reviewed_only: bool = Query(False, description="Chỉ export các segment đã được duyệt"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Export dataset với video đã cắt lại theo timestamps từ annotation.
    
    Trả về file ZIP với cấu trúc:
    - sentence_clips/: Video clips đã cắt theo annotation
    - signer_clips/: Video gốc của signer  
    - sentence_clips_metadata.csv: Metadata đã cập nhật
    """
    # Get dataset
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset không tồn tại")
    
    # Get segments with their latest annotations
    query = db.query(Segment).filter(Segment.dataset_id == dataset_id)
    
    if include_reviewed_only:
        query = query.filter(Segment.status == 'reviewed')
    
    segments = query.order_by(Segment.id).all()
    
    if not segments:
        raise HTTPException(status_code=400, detail="Dataset không có segment nào")
    
    # Create temp directory for export
    export_dir = Path(tempfile.mkdtemp(prefix=f"export_{dataset.name}_"))
    clips_dir = export_dir / "sentence_clips"
    signer_dir = export_dir / "signer_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    signer_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Prepare CSV data
        csv_rows = []
        exported_count = 0
        skipped_count = 0
        signer_videos_exported = set()
        
        for segment in segments:
            # Get latest annotation if exists
            latest_annotation = None
            if segment.annotations:
                latest_annotation = segment.annotations[0]  # Already ordered by desc(version)
            
            # Determine timestamps to use
            if latest_annotation:
                # Use annotated timestamps
                start_time = float(latest_annotation.start_time) if latest_annotation.start_time else float(segment.start_time)
                end_time = float(latest_annotation.end_time) if latest_annotation.end_time else float(segment.end_time)
                final_text = latest_annotation.final_text or segment.asr_text or ''
                gloss_sequence = latest_annotation.gloss_sequence or ''
            else:
                # Use original timestamps
                start_time = float(segment.start_time)
                end_time = float(segment.end_time)
                final_text = segment.asr_text or ''
                gloss_sequence = ''
            
            duration = end_time - start_time
            
            # Find source signer video
            signer_video_name = segment.video_source
            signer_video_path = Path(SIGNER_CLIPS_DIR) / signer_video_name
            
            if not signer_video_path.exists():
                logger.warning(f"Signer video not found: {signer_video_path}")
                skipped_count += 1
                continue
            
            # Copy signer video if not already exported
            if signer_video_name not in signer_videos_exported:
                dest_signer = signer_dir / signer_video_name
                shutil.copy2(signer_video_path, dest_signer)
                signer_videos_exported.add(signer_video_name)
            
            # Cut the clip with new timestamps
            output_clip = clips_dir / f"{segment.clip_name}.mp4"
            success = cut_video_clip(signer_video_path, output_clip, start_time, end_time)
            
            if not success:
                logger.warning(f"Failed to cut clip: {segment.clip_name}")
                skipped_count += 1
                continue
            
            # Add to CSV
            csv_rows.append({
                'name': segment.clip_name,
                'video_source': signer_video_name,
                'segment_id': segment.segment_id or 0,
                'start_original': start_time,
                'start_rounded': int(start_time) + 1 if start_time % 1 > 0 else int(start_time),
                'end_original': end_time,
                'end_rounded': int(end_time) + 1 if end_time % 1 > 0 else int(end_time),
                'end_with_buffer': end_time,  # No buffer for exported data
                'duration': round(duration, 3),
                'is_last_segment': segment.is_last_segment,
                'text': final_text,
                'gloss': gloss_sequence,
                'status': 'success',
                'signer_id': segment.signer_id or 0,
                'split': segment.split or 'train',
                'annotation_status': segment.status,
            })
            exported_count += 1
        
        if exported_count == 0:
            shutil.rmtree(export_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail="Không có segment nào được export thành công")
        
        # Write CSV
        csv_path = export_dir / "sentence_clips_metadata.csv"
        fieldnames = [
            'name', 'video_source', 'segment_id', 'start_original', 'start_rounded',
            'end_original', 'end_rounded', 'end_with_buffer', 'duration',
            'is_last_segment', 'text', 'gloss', 'status', 'signer_id', 'split', 'annotation_status'
        ]
        
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        
        # Create ZIP file
        zip_filename = f"{dataset.name}_exported_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = export_dir / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add sentence clips
            for clip_file in clips_dir.glob("*.mp4"):
                zipf.write(clip_file, f"sentence_clips/{clip_file.name}")
            
            # Add signer clips
            for signer_file in signer_dir.glob("*.mp4"):
                zipf.write(signer_file, f"signer_clips/{signer_file.name}")
            
            # Add CSV
            zipf.write(csv_path, "sentence_clips_metadata.csv")
        
        logger.info(f"Export completed: {exported_count} clips, {len(signer_videos_exported)} signer videos")
        
        # Copy ZIP to a more permanent location for download
        final_zip_dir = Path(DATA_DIR) / "exports"
        final_zip_dir.mkdir(parents=True, exist_ok=True)
        final_zip_path = final_zip_dir / zip_filename
        shutil.copy2(zip_path, final_zip_path)
        
        # Clean up temp directory
        shutil.rmtree(export_dir, ignore_errors=True)
        
        # Return file response
        return FileResponse(
            path=final_zip_path,
            filename=zip_filename,
            media_type="application/zip"
        )
        
    except HTTPException:
        shutil.rmtree(export_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(export_dir, ignore_errors=True)
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi export: {str(e)}")
