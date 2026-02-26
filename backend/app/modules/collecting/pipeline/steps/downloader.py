"""
Step 1: Download video(s) from YouTube.
Supports single videos and playlists with quality filtering and signer detection.
"""
import logging
from pathlib import Path
from typing import List, Optional, Callable

import yt_dlp
from slugify import slugify

from .base import PipelineStep
from ..utils.video import standardize_video_to_mp4, MIN_VIDEO_SIZE_MB
from ..utils.face import (
    has_person,
    extract_frame_at_timestamp,
    ROI_CONFIG,
    TEST_TIMESTAMPS,
)

logger = logging.getLogger(__name__)


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
    import cv2
    
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


class DownloaderStep(PipelineStep):
    """
    Step 1: Download video(s) from YouTube.
    
    Features:
    - Supports single videos and playlists
    - SABR/DASH compatible format handling
    - Quality filtering (minimum size check)
    - Signer presence detection
    - Rate limiting and retry logic
    """
    
    @property
    def name(self) -> str:
        return "Download Videos"
    
    def __init__(
        self,
        work_dir: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ):
        super().__init__(work_dir, progress_callback)
        self.raw_dir = self.ensure_dir(self.work_dir / "raw")
    
    def run(self, youtube_url: str, max_videos: int = 1) -> List[Path]:
        """
        Download video(s) from YouTube.
        
        Args:
            youtube_url: YouTube video or playlist URL
            max_videos: Maximum number of videos to download
            
        Returns:
            List of paths to downloaded video files
        """
        self.update_progress(5, f"Downloading video(s) from YouTube (max: {max_videos})...")
        
        # yt-dlp options compatible with YouTube's SABR/DASH streaming
        ydl_opts = {
            'outtmpl': str(self.raw_dir / '%(id)s_raw.%(ext)s'),
            # Prefer high quality: 1080p > 720p > best available
            'format': 'bestvideo[height>=1080]+bestaudio/bestvideo[height>=720]+bestaudio/bv*+ba/b',
            'merge_output_format': 'mkv',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'noplaylist': False,
            # Fix HTTP 403 Forbidden & rate limiting
            'check_formats': 'selected',
            'source_address': '0.0.0.0',
            'sleep_interval': 3,
            'max_sleep_interval': 6,
            'extractor_retries': 5,
            'retries': 5,
            'fragment_retries': 10,
        }
        
        if max_videos and max_videos > 0:
            ydl_opts['playlistend'] = max_videos
        
        downloaded_files = []
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first
                info = ydl.extract_info(youtube_url, download=False)
                
                entries = []
                if 'entries' in info:
                    entries = list(info['entries'])[:max_videos]
                    self.update_progress(8, f"Found playlist with {len(entries)} video(s) to process")
                else:
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
                        
                        # Find raw file
                        raw_candidates = [
                            p for p in self.raw_dir.glob(f"{video_id}_raw.*")
                            if not p.name.endswith(".part")
                        ]
                        
                        if not raw_candidates:
                            logger.warning(f"No raw file found for {video_id}")
                            continue
                        
                        raw_file = max(raw_candidates, key=lambda p: p.stat().st_size)
                        final_mp4 = self.raw_dir / f"{video_id}_final.mp4"
                        
                        # Standardize to OpenCV-friendly MP4
                        self.update_progress(11 + idx, f"Converting video {idx+1} to MP4...")
                        if not standardize_video_to_mp4(raw_file, final_mp4):
                            logger.warning(f"Failed to standardize {raw_file.name}")
                            raw_file.unlink(missing_ok=True)
                            continue
                        
                        # Remove raw file
                        raw_file.unlink(missing_ok=True)
                        
                        # Check video quality (size check)
                        converted_size_mb = final_mp4.stat().st_size / (1024 * 1024)
                        if converted_size_mb < MIN_VIDEO_SIZE_MB:
                            logger.warning(f"Video too small ({converted_size_mb:.1f}MB < {MIN_VIDEO_SIZE_MB}MB), skipping: {original_title}")
                            final_mp4.unlink(missing_ok=True)
                            continue
                        
                        # Check for signer
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
                        
                        # Rename to slugified name
                        final_mp4.rename(new_path)
                        logger.info(f"  Saved as: {new_filename}")
                        
                        downloaded_files.append(new_path)
                        
                    except Exception as e:
                        logger.error(f"Error downloading {video_id}: {e}")
                        # Clean up temp/raw files
                        for pattern in [f"{video_id}_raw.*", f"{video_id}_final.mp4"]:
                            for f in self.raw_dir.glob(pattern):
                                f.unlink(missing_ok=True)
                        continue
                
                self.update_progress(15, f"Downloaded {len(downloaded_files)} video(s)")
                return downloaded_files
                
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return downloaded_files

