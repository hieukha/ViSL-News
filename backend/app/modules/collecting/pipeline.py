#!/usr/bin/env python3
"""
Video Processing Pipeline for ViSL Tool
Downloads YouTube video, crops signer, transcribes, splits into sentence clips,
and clusters signers using face recognition.
- Uses InsightFace for face detection (GPU accelerated)
"""
import os
import json
import csv
import math
import subprocess
import shutil
import zipfile
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple
import logging

import yt_dlp
import cv2
import numpy as np
from slugify import slugify

from ...core.config import HF_HOME

# Try to import InsightFace for GPU-accelerated face detection
try:
    import insightface
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    INSIGHTFACE_AVAILABLE = False

# Set cache directory
os.environ['HF_HOME'] = HF_HOME

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Signer ROI coordinates (x, y, width, height)
SIGNER_ROI = {
    'x': 50,
    'y': 600,
    'width': 327,
    'height': 426
}

# Face detection for signer check (Haar Cascade as fallback)
FACE_XML = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
FACE_CLF = cv2.CascadeClassifier(FACE_XML)

# Detection config
ROI_CONFIG = {'x': 125, 'y': 637, 'width': 178, 'height': 159}
TEST_TIMESTAMPS = [2, 10, 20]

# Quality settings
MIN_VIDEO_SIZE_MB = 5  # Video nhỏ hơn 5MB coi như chất lượng thấp
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080

# =========================
# Face detector (InsightFace with GPU support)
# =========================
_insightface_model = None


def get_insightface_model():
    """Get or initialize InsightFace model (singleton pattern)"""
    global _insightface_model
    if _insightface_model is None and INSIGHTFACE_AVAILABLE:
        try:
            # Try GPU first (CUDA), fallback to CPU
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            _insightface_model = insightface.app.FaceAnalysis(
                name='buffalo_l',  # High accuracy model
                providers=providers
            )
            _insightface_model.prepare(ctx_id=0, det_size=(640, 640))
            logger.info("✓ InsightFace model loaded (GPU accelerated)")
        except Exception as e:
            logger.warning(f"Failed to load InsightFace model: {e}")
            _insightface_model = False  # Mark as failed
    return _insightface_model if _insightface_model is not False else None


def detect_face_insightface(img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect face using InsightFace (GPU accelerated).
    
    Args:
        img: Input image (BGR format)
        
    Returns:
        (x, y, w, h) bounding box of the largest face, or None if no face detected
    """
    model = get_insightface_model()
    if model is None:
        return None
    
    try:
        # InsightFace expects BGR format (same as OpenCV)
        faces = model.get(img)
        
        if len(faces) > 0:
            # Return the largest face
            largest_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            bbox = largest_face.bbox.astype(int)
            x, y, x2, y2 = bbox
            w, h = x2 - x, y2 - y
            return (x, y, w, h)
    except Exception as e:
        logger.debug(f"InsightFace detection error: {e}")
    
    return None


def detect_face_haar(img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Fallback face detection using OpenCV Haar Cascade.
    
    Args:
        img: Input image (BGR format)
        
    Returns:
        (x, y, w, h) bounding box of the largest face, or None if no face detected
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    
    faces = FACE_CLF.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=6,
        minSize=(40, 40),
    )
    
    if len(faces) > 0:
        # Return the largest face
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest_face
        return (x, y, w, h)
    
    return None


def has_person(img: np.ndarray) -> bool:
    """
    Check if a person (face) is present in the image.
    Uses InsightFace (GPU) if available, falls back to Haar Cascade.
    
    Args:
        img: Input image (BGR format)
        
    Returns:
        True if a face is detected, False otherwise
    """
    # Try InsightFace first (better accuracy, GPU accelerated)
    if INSIGHTFACE_AVAILABLE:
        face_box = detect_face_insightface(img)
        if face_box is not None:
            return True
    
    # Fallback to Haar Cascade if InsightFace fails or not available
    face_box = detect_face_haar(img)
    return face_box is not None


def extract_frame_at_timestamp(video_path: str, timestamp: float) -> Optional[np.ndarray]:
    """Extract a single frame from video at given timestamp"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_number = int(timestamp * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def check_video_has_signer(video_path: str) -> bool:
    """
    Check if video has signer in ROI across test frames.
    Test 3 frames at seconds 2, 10, 20.
    Only returns True if ALL 3 frames detect a person in the ROI.
    
    Args:
        video_path: Path to video file
    
    Returns:
        True if all 3 frames have a person in ROI
    """
    logger.info(f"Checking for signer in video: {video_path}")
    
    roi = ROI_CONFIG
    results = []
    
    for timestamp in TEST_TIMESTAMPS:
        frame = extract_frame_at_timestamp(video_path, timestamp)
        
        if frame is None:
            logger.warning(f"  Failed to extract frame at {timestamp}s")
            return False
        
        h, w = frame.shape[:2]
        if w != 1920 or h != 1080:
            logger.warning(f"  Frame size mismatch: expected 1920x1080, got {w}x{h}")
            frame = cv2.resize(frame, (1920, 1080))
        
        x, y, width, height = roi['x'], roi['y'], roi['width'], roi['height']
        roi_frame = frame[y:y+height, x:x+width]
        
        has_signer = has_person(roi_frame)
        results.append(has_signer)
        
        logger.info(f"  Frame at {timestamp}s: {'✓ Has signer' if has_signer else '✗ No signer'}")
    
    # Only return True if ALL 3 frames have a person
    all_have_signer = all(results)
    logger.info(f"Signer detection result: {'✓ PASS' if all_have_signer else '✗ FAIL'} ({sum(results)}/3 frames)")
    
    return all_have_signer


def get_video_duration(video_path: Path) -> Optional[float]:
    """Get video duration using ffprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except:
        return None


def standardize_video_to_mp4(raw_path: Path, final_path: Path) -> bool:
    """
    Convert any DASH/webm/mkv/mp4 input into a stable OpenCV-friendly MP4.
    This is needed because YouTube now uses SABR streaming.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(raw_path),
        "-movflags", "+faststart",
        "-vsync", "cfr",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-c:a", "aac",
        str(final_path),
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return final_path.exists() and final_path.stat().st_size > 0
    except Exception as e:
        logger.error(f"ffmpeg standardize failed for {raw_path.name}: {e}")
        return False


class VideoPipeline:
    """End-to-end video processing pipeline"""
    
    def __init__(self, work_dir: Path, progress_callback: Optional[Callable] = None):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.progress_callback = progress_callback
        
        # Sub directories
        self.raw_dir = self.work_dir / "raw"
        self.signer_dir = self.work_dir / "signer_clips"
        self.transcripts_dir = self.work_dir / "transcripts"
        self.clips_dir = self.work_dir / "sentence_clips"
        self.metadata_file = self.work_dir / "sentence_clips_metadata.csv"
        
        for d in [self.raw_dir, self.signer_dir, self.transcripts_dir, self.clips_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    def update_progress(self, percent: int, message: str):
        """Update progress"""
        logger.info(f"[{percent}%] {message}")
        if self.progress_callback:
            self.progress_callback(percent, message)
    
    def step1_download_video(self, youtube_url: str, max_videos: int = 1) -> List[Path]:
        """Download video(s) from YouTube (supports single video or playlist)
        
        Uses SABR/DASH compatible format and ffmpeg standardization
        to handle YouTube's new streaming protocol.
        """
        self.update_progress(5, f"Downloading video(s) from YouTube (max: {max_videos})...")
        
        # Use format compatible with YouTube's SABR/DASH streaming
        # Better options with rate limiting and retries (matching data_collection.py)
        ydl_opts = {
            'outtmpl': str(self.raw_dir / '%(id)s_raw.%(ext)s'),
            # Ưu tiên chất lượng cao: 1080p > 720p > best available
            'format': 'bestvideo[height>=1080]+bestaudio/bestvideo[height>=720]+bestaudio/bv*+ba/b',
            'merge_output_format': 'mkv',      # Stable container for merging
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'noplaylist': False,
            # === Fix HTTP 403 Forbidden & rate limiting ===
            'check_formats': 'selected',       # Kiểm tra format trước khi tải
            'source_address': '0.0.0.0',       # Force IPv4
            'sleep_interval': 3,               # Đợi 3s giữa các video
            'max_sleep_interval': 6,           # Tối đa 6s
            'extractor_retries': 5,            # Retry 5 lần nếu fail
            'retries': 5,                      # Retry download 5 lần
            'fragment_retries': 10,            # Retry fragment 10 lần (cho HLS/m3u8)
        }
        
        if max_videos and max_videos > 0:
            ydl_opts['playlistend'] = max_videos
        
        downloaded_files = []
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first to check if it's a playlist
                info = ydl.extract_info(youtube_url, download=False)
                
                entries = []
                if 'entries' in info:
                    # It's a playlist
                    entries = list(info['entries'])[:max_videos]
                    self.update_progress(8, f"Found playlist with {len(entries)} video(s) to process")
                else:
                    # Single video
                    entries = [info]
                
                # Download each video
                for idx, entry in enumerate(entries):
                    if not entry:
                        continue
                    
                    video_id = entry.get('id', f'video_{idx}')
                    original_title = entry.get('title', 'untitled')
                    video_url = entry.get('webpage_url') or f"https://www.youtube.com/watch?v={video_id}"
                    
                    self.update_progress(10 + idx, f"Downloading video {idx+1}/{len(entries)}: {original_title[:30]}...")
                    
                    try:
                        ydl.download([video_url])
                        
                        # Find raw file (could be mkv, webm, mp4, etc.)
                        raw_candidates = [
                            p for p in self.raw_dir.glob(f"{video_id}_raw.*")
                            if not p.name.endswith(".part")
                        ]
                        
                        if not raw_candidates:
                            logger.warning(f"No raw file found for {video_id}")
                            continue
                        
                        raw_file = max(raw_candidates, key=lambda p: p.stat().st_size)
                        final_mp4 = self.raw_dir / f"{video_id}_final.mp4"
                        
                        # Standardize to OpenCV-friendly MP4 using ffmpeg
                        self.update_progress(11 + idx, f"Converting video {idx+1} to MP4...")
                        if not standardize_video_to_mp4(raw_file, final_mp4):
                            logger.warning(f"Failed to standardize {raw_file.name}")
                            raw_file.unlink(missing_ok=True)
                            continue
                        
                        # Remove raw file after successful conversion
                        raw_file.unlink(missing_ok=True)
                        
                        # Check video quality (size check)
                        converted_size_mb = final_mp4.stat().st_size / (1024 * 1024)
                        if converted_size_mb < MIN_VIDEO_SIZE_MB:
                            logger.warning(f"Video too small ({converted_size_mb:.1f}MB < {MIN_VIDEO_SIZE_MB}MB), skipping: {original_title}")
                            final_mp4.unlink(missing_ok=True)
                            continue
                        
                        # Check for signer - must pass ALL 3 test frames
                        self.update_progress(12 + idx, f"Checking for signer in video {idx+1}...")
                        has_signer = check_video_has_signer(str(final_mp4))
                        
                        if not has_signer:
                            logger.info(f"✗ No signer detected in {final_mp4.name} - skipping video")
                            final_mp4.unlink(missing_ok=True)
                            continue
                        
                        logger.info(f"✓ Signer detected - saving video")
                        
                        # Create slugified filename
                        slug_title = slugify(original_title)
                        new_filename = f"{slug_title}.mp4"
                        new_path = self.raw_dir / new_filename
                        
                        # Handle duplicate filenames
                        counter = 1
                        while new_path.exists():
                            new_filename = f"{slug_title}-{counter}.mp4"
                            new_path = self.raw_dir / new_filename
                            counter += 1
                        
                        # Rename the final file to slugified name
                        final_mp4.rename(new_path)
                        logger.info(f"  Saved as: {new_filename}")
                        
                        downloaded_files.append(new_path)
                        
                    except Exception as e:
                        logger.error(f"Error downloading {video_id}: {e}")
                        # Clean up any temp/raw files
                        for pattern in [f"{video_id}_raw.*", f"{video_id}_final.mp4"]:
                            for f in self.raw_dir.glob(pattern):
                                f.unlink(missing_ok=True)
                        continue
                
                self.update_progress(15, f"Downloaded {len(downloaded_files)} video(s)")
                return downloaded_files
                
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return downloaded_files
    
    def step2_crop_signer(self, video_path: Path) -> Optional[Path]:
        """Crop signer ROI from video"""
        self.update_progress(20, "Cropping signer region...")
        
        output_file = self.signer_dir / f"signer_{video_path.name}"
        
        try:
            roi = SIGNER_ROI
            cmd = [
                'ffmpeg', '-y',
                '-i', str(video_path),
                '-filter:v', f"crop={roi['width']}:{roi['height']}:{roi['x']}:{roi['y']}",
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                str(output_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode == 0 and output_file.exists():
                self.update_progress(35, f"Cropped signer: {output_file.name}")
                return output_file
            else:
                logger.error(f"ffmpeg error: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Error cropping video: {e}")
            return None
    
    def step3_transcribe(self, video_path: Path) -> Optional[Path]:
        """Transcribe video using WhisperX"""
        self.update_progress(40, "Loading transcription model...")
        
        try:
            import whisperx
            import torch
            import gc
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            
            # Load model
            model = whisperx.load_model("large-v3", device, compute_type=compute_type)
            
            self.update_progress(50, "Transcribing audio...")
            
            # Load audio and transcribe
            audio = whisperx.load_audio(str(video_path))
            result = model.transcribe(audio, batch_size=16, language="vi")
            
            # Align
            self.update_progress(55, "Aligning timestamps...")
            try:
                align_model, metadata = whisperx.load_align_model(language_code="vi", device=device)
                result = whisperx.align(result["segments"], align_model, metadata, audio, device, return_char_alignments=False)
            except:
                logger.warning("Could not load alignment model, using raw transcription")
            
            # Save
            video_name = video_path.stem
            if video_name.startswith("signer_"):
                video_name = video_name[7:]
            
            output_file = self.transcripts_dir / f"{video_name}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            # Cleanup
            del model, audio
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            self.update_progress(65, f"Transcribed: {len(result.get('segments', []))} segments")
            return output_file
            
        except Exception as e:
            logger.error(f"Error transcribing: {e}")
            return None
    
    def step4_split_clips(self, video_path: Path, transcript_path: Path) -> List[Dict]:
        """Split video into sentence clips"""
        self.update_progress(70, "Splitting into sentence clips...")
        
        metadata_list = []
        
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript = json.load(f)
            
            segments = transcript.get('segments', [])
            if not segments:
                logger.warning("No segments found")
                return []
            
            video_duration = get_video_duration(video_path)
            if not video_duration:
                video_duration = 9999
            
            base_name = video_path.stem
            if base_name.startswith('signer_'):
                base_name = base_name[7:]
            
            end_buffer = 2.0
            total_segments = len(segments)
            
            for idx, segment in enumerate(segments):
                start_original = segment.get('start', 0)
                end_original = segment.get('end', 0)
                text = segment.get('text', '').strip()
                
                start = math.ceil(start_original)
                end_rounded = math.ceil(end_original)
                
                is_last = (idx == total_segments - 1)
                end_with_buffer = min(end_rounded + (0 if is_last else end_buffer), video_duration)
                
                if end_rounded <= start or start < 0:
                    continue
                
                output_filename = f"{base_name}-{idx}.mp4"
                output_path = self.clips_dir / output_filename
                
                # Cut clip
                duration = end_with_buffer - start
                cmd = [
                    'ffmpeg', '-y',
                    '-i', str(video_path),
                    '-ss', str(start),
                    '-t', str(duration),
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    '-crf', '23',
                    '-c:a', 'copy',
                    str(output_path)
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                status = 'success' if result.returncode == 0 else 'failed'
                
                metadata_list.append({
                    'name': f"{base_name}-{idx}",
                    'video_source': video_path.name,
                    'segment_id': idx,
                    'start_original': start_original,
                    'start_rounded': start,
                    'end_original': end_original,
                    'end_rounded': end_rounded,
                    'end_with_buffer': end_with_buffer,
                    'duration': duration,
                    'is_last_segment': is_last,
                    'text': text,
                    'status': status
                })
                
                # Update progress
                progress = 70 + int((idx / total_segments) * 15)
                self.update_progress(progress, f"Cutting clip {idx+1}/{total_segments}")
            
            # Save metadata CSV
            self.update_progress(85, "Saving metadata...")
            fieldnames = ['name', 'video_source', 'segment_id', 'start_original', 'start_rounded',
                         'end_original', 'end_rounded', 'end_with_buffer', 'duration',
                         'is_last_segment', 'text', 'status']
            
            with open(self.metadata_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(metadata_list)
            
            return metadata_list
            
        except Exception as e:
            logger.error(f"Error splitting clips: {e}")
            return []
    
    def step5_face_clustering(self) -> bool:
        """
        Cluster signers using face recognition - REQUIRED STEP.
        Identifies and assigns signer IDs to each clip.
        """
        self.update_progress(80, "Starting face clustering (required step)...")
        
        try:
            # Import face clustering functions from local module
            from .face_clustering import (
                extract_all_embeddings,
                cluster_embeddings,
                update_metadata_with_signers,
                INSIGHTFACE_AVAILABLE
            )
            
            # Check InsightFace availability
            if INSIGHTFACE_AVAILABLE:
                logger.info("Face clustering: Using InsightFace + DBSCAN")
            else:
                logger.error("Face clustering: InsightFace not available!")
                raise Exception("InsightFace is required for face clustering")
            
            # Extract embeddings from all clips
            self.update_progress(82, "Extracting face embeddings from clips...")
            embeddings_file = self.work_dir / "face_embeddings.pkl"
            
            embeddings_dict = extract_all_embeddings(
                clips_dir=self.clips_dir,
                metadata_file=self.metadata_file,
                embeddings_file=embeddings_file,
                max_clips=None
            )
            
            if not embeddings_dict:
                logger.error("Face clustering failed: No embeddings extracted from clips")
                raise Exception("Face clustering failed: Could not extract face embeddings from any clips")
            
            logger.info(f"Extracted embeddings from {len(embeddings_dict)} clips")
            
            # Cluster embeddings using DBSCAN
            self.update_progress(88, f"Clustering {len(embeddings_dict)} face embeddings...")
            signer_assignments = cluster_embeddings(embeddings_dict)
            
            if not signer_assignments:
                logger.error("Face clustering failed: Clustering returned no results")
                raise Exception("Face clustering failed: No signers identified")
            
            n_signers = len(set(signer_assignments.values()))
            logger.info(f"Identified {n_signers} unique signer(s)")
            
            # Update metadata with signer IDs
            self.update_progress(92, "Updating metadata with signer IDs...")
            update_metadata_with_signers(
                metadata_file=self.metadata_file,
                output_file=self.metadata_file,  # Overwrite with signer_id column
                signer_assignments=signer_assignments
            )
            
            # Save cluster results JSON
            cluster_results_file = self.work_dir / "cluster_results.json"
            signer_groups = {}
            for clip_name, signer_id in signer_assignments.items():
                if signer_id not in signer_groups:
                    signer_groups[signer_id] = []
                signer_groups[signer_id].append(clip_name)
            
            cluster_results = {
                'total_clips': len(signer_assignments),
                'n_signers': n_signers,
                'signer_groups': {str(k): v for k, v in signer_groups.items()},
                'clustering_method': 'dbscan'
            }
            
            with open(cluster_results_file, 'w', encoding='utf-8') as f:
                json.dump(cluster_results, f, ensure_ascii=False, indent=2)
            
            self.update_progress(95, f"Face clustering complete: {n_signers} signer(s) identified in {len(signer_assignments)} clips")
            return True
            
        except ImportError as e:
            logger.error(f"Face clustering import error: {e}")
            logger.error("Make sure dependencies are installed: pip install insightface onnxruntime scikit-learn")
            raise Exception(f"Face clustering failed (import error): {e}")
        except Exception as e:
            logger.error(f"Face clustering error: {e}")
            # Don't fail silently - this is a required step
            raise Exception(f"Face clustering failed (required step): {e}")
    
    def step6_create_zip(self) -> Optional[Path]:
        """Create ZIP archive with clips, signer videos, metadata and clustering results"""
        self.update_progress(96, "Creating ZIP archive...")
        
        zip_path = self.work_dir / "result.zip"
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add sentence clips
                for video_file in self.clips_dir.glob("*.mp4"):
                    zipf.write(video_file, f"sentence_clips/{video_file.name}")
                
                # Add signer videos (cropped videos containing signer)
                for video_file in self.signer_dir.glob("*.mp4"):
                    zipf.write(video_file, f"signer_clips/{video_file.name}")
                
                # Add metadata CSV (now includes signer_id column)
                if self.metadata_file.exists():
                    zipf.write(self.metadata_file, "sentence_clips_metadata.csv")
            
                # Add face clustering results
                cluster_results_file = self.work_dir / "cluster_results.json"
                if cluster_results_file.exists():
                    zipf.write(cluster_results_file, "cluster_results.json")
                
                # Add face embeddings (for future analysis)
                embeddings_file = self.work_dir / "face_embeddings.pkl"
                if embeddings_file.exists():
                    zipf.write(embeddings_file, "face_embeddings.pkl")
            
            self.update_progress(99, f"ZIP created: {zip_path.name}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Error creating ZIP: {e}")
            return None
    
    def run(self, youtube_url: str, max_videos: int = 1) -> Optional[Path]:
        """
        Run the complete pipeline for one or more videos.
        
        Pipeline steps:
        1. Download video(s) from YouTube
        2. Crop signer region
        3. Transcribe audio (WhisperX)
        4. Split into sentence clips
        5. Face clustering (REQUIRED) - identify signers
        6. Create ZIP archive
        """
        self.update_progress(0, "Starting pipeline...")
        
        # Step 1: Download video(s)
        video_paths = self.step1_download_video(youtube_url, max_videos)
        if not video_paths:
            logger.error("No videos downloaded")
            return None
        
        total_videos = len(video_paths)
        all_metadata = []
        
        # Process each video (steps 2-4)
        for idx, video_path in enumerate(video_paths):
            video_num = idx + 1
            base_progress = 15 + int((idx / total_videos) * 55)  # 15-70% (reduced to make room for clustering)
            
            self.update_progress(base_progress, f"Processing video {video_num}/{total_videos}: {video_path.name}")
            
            # Step 2: Crop signer
            self.update_progress(base_progress + 5, f"[{video_num}/{total_videos}] Cropping signer...")
            signer_video = self.step2_crop_signer(video_path)
            if not signer_video:
                logger.warning(f"Failed to crop {video_path.name}, skipping...")
                continue
            
            # Step 3: Transcribe
            self.update_progress(base_progress + 15, f"[{video_num}/{total_videos}] Transcribing...")
            transcript_path = self.step3_transcribe(signer_video)
            if not transcript_path:
                logger.warning(f"Failed to transcribe {video_path.name}, skipping...")
                continue
            
            # Step 4: Split into clips
            self.update_progress(base_progress + 25, f"[{video_num}/{total_videos}] Splitting clips...")
            metadata = self.step4_split_clips(signer_video, transcript_path)
            if metadata:
                all_metadata.extend(metadata)
            else:
                logger.warning(f"No clips generated for {video_path.name}")
        
        # Check if we have any clips to process
        if not all_metadata:
            logger.error("No clips generated from any video")
            return None
        
        # Save combined metadata (before clustering)
        self.update_progress(75, "Saving combined metadata...")
        fieldnames = ['name', 'video_source', 'segment_id', 'start_original', 'start_rounded',
                     'end_original', 'end_rounded', 'end_with_buffer', 'duration',
                     'is_last_segment', 'text', 'status']
        
        with open(self.metadata_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_metadata)
        
        # Step 5: Face Clustering (REQUIRED)
        try:
            self.step5_face_clustering()
        except Exception as e:
            logger.error(f"Pipeline failed at face clustering: {e}")
            self.update_progress(100, f"Pipeline failed: Face clustering error - {e}")
            return None  # Fail the entire pipeline if clustering fails
        
        # Step 6: Create ZIP
        zip_path = self.step6_create_zip()
        
        self.update_progress(100, f"Pipeline complete! Processed {total_videos} video(s), {len(all_metadata)} clips with signer IDs")
        return zip_path
    
    def cleanup(self):
        """Clean up work directory"""
        try:
            shutil.rmtree(self.work_dir)
        except:
            pass

