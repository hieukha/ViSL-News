"""
Step 6: Create ZIP archive with results.
"""
import zipfile
import logging
from pathlib import Path
from typing import Optional, Callable

from .base import PipelineStep

logger = logging.getLogger(__name__)


class ArchiverStep(PipelineStep):
    """
    Step 6: Create ZIP archive with all results.
    
    Packages:
    - Sentence clips
    - Signer clips (cropped videos)
    - Metadata CSV (with signer IDs)
    - Cluster results JSON
    - Face embeddings (for future analysis)
    """
    
    @property
    def name(self) -> str:
        return "Create Archive"
    
    def __init__(
        self,
        work_dir: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ):
        super().__init__(work_dir, progress_callback)
        self.clips_dir = self.work_dir / "sentence_clips"
        self.signer_dir = self.work_dir / "signer_clips"
        self.metadata_file = self.work_dir / "sentence_clips_metadata.csv"
        self.cluster_results_file = self.work_dir / "cluster_results.json"
        self.embeddings_file = self.work_dir / "face_embeddings.pkl"
    
    def run(self) -> Optional[Path]:
        """
        Create ZIP archive with all results.
        
        Returns:
            Path to ZIP file, or None if failed
        """
        self.update_progress(96, "Creating ZIP archive...")
        
        zip_path = self.work_dir / "result.zip"
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add sentence clips
                if self.clips_dir.exists():
                    for video_file in self.clips_dir.glob("*.mp4"):
                        zipf.write(video_file, f"sentence_clips/{video_file.name}")
                
                # Add signer videos (cropped videos)
                if self.signer_dir.exists():
                    for video_file in self.signer_dir.glob("*.mp4"):
                        zipf.write(video_file, f"signer_clips/{video_file.name}")
                
                # Add metadata CSV (includes signer_id column)
                if self.metadata_file.exists():
                    zipf.write(self.metadata_file, "sentence_clips_metadata.csv")
                
                # Add face clustering results
                if self.cluster_results_file.exists():
                    zipf.write(self.cluster_results_file, "cluster_results.json")
                
                # Add face embeddings (for future analysis)
                if self.embeddings_file.exists():
                    zipf.write(self.embeddings_file, "face_embeddings.pkl")
            
            self.update_progress(99, f"ZIP created: {zip_path.name}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Error creating ZIP: {e}")
            return None

