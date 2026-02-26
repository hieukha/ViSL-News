"""
Video processing utilities.
Provides ffmpeg wrappers and video configuration constants.
"""
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# =========================
# Constants
# =========================

# Signer ROI coordinates (x, y, width, height)
SIGNER_ROI = {
    'x': 50,
    'y': 600,
    'width': 327,
    'height': 426
}

# Quality settings
MIN_VIDEO_SIZE_MB = 5  # Video nhỏ hơn 5MB coi như chất lượng thấp
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080


# =========================
# Video Processing Functions
# =========================

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


def crop_video(
    input_path: Path,
    output_path: Path,
    roi: dict,
    preset: str = 'fast',
    crf: int = 23
) -> bool:
    """
    Crop video to specified ROI using ffmpeg.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        roi: Dictionary with 'x', 'y', 'width', 'height' keys
        preset: FFmpeg preset (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)
        crf: Constant Rate Factor (0-51, lower = better quality)
        
    Returns:
        True if successful, False otherwise
    """
    cmd = [
        'ffmpeg', '-y',
        '-i', str(input_path),
        '-filter:v', f"crop={roi['width']}:{roi['height']}:{roi['x']}:{roi['y']}",
        '-c:a', 'copy',
        '-c:v', 'libx264',
        '-preset', preset,
        '-crf', str(crf),
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode == 0 and output_path.exists()
    except Exception as e:
        logger.error(f"Error cropping video: {e}")
        return False


def cut_video_segment(
    input_path: Path,
    output_path: Path,
    start_time: float,
    duration: float,
    preset: str = 'fast',
    crf: int = 23
) -> bool:
    """
    Cut a segment from video using ffmpeg.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        start_time: Start time in seconds
        duration: Duration in seconds
        preset: FFmpeg preset
        crf: Constant Rate Factor
        
    Returns:
        True if successful, False otherwise
    """
    cmd = [
        'ffmpeg', '-y',
        '-i', str(input_path),
        '-ss', str(start_time),
        '-t', str(duration),
        '-c:v', 'libx264',
        '-preset', preset,
        '-crf', str(crf),
        '-c:a', 'copy',
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode == 0 and output_path.exists()
    except Exception as e:
        logger.error(f"Error cutting video segment: {e}")
        return False

