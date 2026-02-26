"""
Step 2: Preprocess video - crop signer region.
"""
import logging
from pathlib import Path
from typing import Optional, Callable

from .base import PipelineStep
from ..utils.video import SIGNER_ROI, crop_video

logger = logging.getLogger(__name__)


class PreprocessorStep(PipelineStep):
    """
    Step 2: Crop signer ROI from video.
    
    Extracts the signer region from the full video frame
    using predefined ROI coordinates.
    """
    
    @property
    def name(self) -> str:
        return "Crop Signer"
    
    def __init__(
        self,
        work_dir: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ):
        super().__init__(work_dir, progress_callback)
        self.signer_dir = self.ensure_dir(self.work_dir / "signer_clips")
    
    def run(self, video_path: Path) -> Optional[Path]:
        """
        Crop signer ROI from video.
        
        Args:
            video_path: Path to input video
            
        Returns:
            Path to cropped signer video, or None if failed
        """
        self.update_progress(20, "Cropping signer region...")
        
        output_file = self.signer_dir / f"signer_{video_path.name}"
        
        try:
            success = crop_video(
                input_path=video_path,
                output_path=output_file,
                roi=SIGNER_ROI,
                preset='fast',
                crf=23
            )
            
            if success and output_file.exists():
                self.update_progress(35, f"Cropped signer: {output_file.name}")
                return output_file
            else:
                logger.error(f"Failed to crop video: {video_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error cropping video: {e}")
            return None

