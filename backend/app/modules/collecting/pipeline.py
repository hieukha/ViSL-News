#!/usr/bin/env python3
"""
Video Processing Pipeline for ViSL Tool
Downloads YouTube video, crops signer, transcribes, splits into sentence clips
"""
import os
import json
import csv
import math
import subprocess
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Callable
import logging

import yt_dlp
import cv2
import numpy as np
from slugify import slugify

from ...core.config import HF_HOME

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

# Face detection for signer check
FACE_XML = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
FACE_CLF = cv2.CascadeClassifier(FACE_XML)

# Detection config
ROI_CONFIG = {'x': 125, 'y': 637, 'width': 178, 'height': 159}
TEST_TIMESTAMPS = [2, 10, 20]


def has_person(img: np.ndarray, minNeighbors: int = 6, minSize: tuple = (40, 40)) -> bool:
    """Detect if there's a face in the image"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    faces = FACE_CLF.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=minNeighbors, minSize=minSize)
    return len(faces) > 0


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
        """Download video(s) from YouTube (supports single video or playlist)"""
        self.update_progress(5, f"Downloading video(s) from YouTube (max: {max_videos})...")
        
        # Use temp filename for downloading - will rename after signer check
        ydl_opts = {
            'outtmpl': str(self.raw_dir / '%(id)s_temp.%(ext)s'),
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
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
                        
                        # Find the temporary file
                        temp_file = self.raw_dir / f"{video_id}_temp.mp4"
                        if not temp_file.exists():
                            temp_file = self.raw_dir / f"{video_id}_temp.webm"
                        
                        if temp_file.exists():
                            # Check for signer - must pass ALL 3 test frames
                            self.update_progress(12 + idx, f"Checking for signer in video {idx+1}...")
                            has_signer = check_video_has_signer(str(temp_file))
                            
                            if not has_signer:
                                logger.info(f"✗ No signer detected in {temp_file.name} - skipping video")
                                # Delete the temporary file since it doesn't have a signer
                                try:
                                    os.remove(temp_file)
                                    logger.info(f"  Deleted: {temp_file.name}")
                                except Exception as del_e:
                                    logger.warning(f"  Could not delete {temp_file.name}: {del_e}")
                                continue  # Skip to next video
                            
                            logger.info(f"✓ Signer detected - saving video")
                            
                            # Create slugified filename (like data_collection.py)
                            slug_title = slugify(original_title)
                            new_filename = f"{slug_title}.mp4"
                            new_path = self.raw_dir / new_filename
                            
                            # Handle duplicate filenames
                            counter = 1
                            while new_path.exists():
                                new_filename = f"{slug_title}-{counter}.mp4"
                                new_path = self.raw_dir / new_filename
                                counter += 1
                            
                            # Rename the file from temp to slugified name
                            os.rename(temp_file, new_path)
                            logger.info(f"  Saved as: {new_filename}")
                            
                            downloaded_files.append(new_path)
                    except Exception as e:
                        logger.error(f"Error downloading {video_id}: {e}")
                        # Clean up temp file if it exists
                        temp_file = self.raw_dir / f"{video_id}_temp.mp4"
                        if temp_file.exists():
                            try:
                                os.remove(temp_file)
                            except:
                                pass
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
    
    def step5_create_zip(self) -> Optional[Path]:
        """Create ZIP archive with clips and metadata"""
        self.update_progress(90, "Creating ZIP archive...")
        
        zip_path = self.work_dir / "result.zip"
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add video clips
                for video_file in self.clips_dir.glob("*.mp4"):
                    zipf.write(video_file, f"sentence_clips/{video_file.name}")
                
                # Add metadata CSV
                if self.metadata_file.exists():
                    zipf.write(self.metadata_file, "sentence_clips_metadata.csv")
            
            self.update_progress(95, f"ZIP created: {zip_path.name}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Error creating ZIP: {e}")
            return None
    
    def run(self, youtube_url: str, max_videos: int = 1) -> Optional[Path]:
        """Run the complete pipeline for one or more videos"""
        self.update_progress(0, "Starting pipeline...")
        
        # Step 1: Download video(s)
        video_paths = self.step1_download_video(youtube_url, max_videos)
        if not video_paths:
            logger.error("No videos downloaded")
            return None
        
        total_videos = len(video_paths)
        all_metadata = []
        
        # Process each video
        for idx, video_path in enumerate(video_paths):
            video_num = idx + 1
            base_progress = 15 + int((idx / total_videos) * 70)  # 15-85%
            
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
        
        # Save combined metadata
        if all_metadata:
            self.update_progress(88, "Saving combined metadata...")
            fieldnames = ['name', 'video_source', 'segment_id', 'start_original', 'start_rounded',
                         'end_original', 'end_rounded', 'end_with_buffer', 'duration',
                         'is_last_segment', 'text', 'status']
            
            with open(self.metadata_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_metadata)
        
        # Step 5: Create ZIP
        zip_path = self.step5_create_zip()
        
        self.update_progress(100, f"Pipeline complete! Processed {total_videos} video(s), {len(all_metadata)} clips")
        return zip_path
    
    def cleanup(self):
        """Clean up work directory"""
        try:
            shutil.rmtree(self.work_dir)
        except:
            pass

