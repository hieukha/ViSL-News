"""
Video Processing Pipeline Orchestrator.
Manages the sequence of pipeline steps for video processing.

Pipeline Steps:
1. Download - Download video(s) from YouTube
2. Preprocess - Crop signer region
3. Transcribe - Transcribe audio using WhisperX
4. Split - Split into sentence clips
5. Cluster - Face clustering to identify signers
6. Archive - Create ZIP with results
"""
import csv
import shutil
import logging
from pathlib import Path
from typing import Optional, Callable, List, Dict

from .steps import (
    DownloaderStep,
    PreprocessorStep,
    TranscriberStep,
    SplitterStep,
    ClustererStep,
    ArchiverStep,
)

logger = logging.getLogger(__name__)


class VideoPipeline:
    """
    End-to-end video processing pipeline.
    
    Orchestrates the execution of pipeline steps:
    1. Download video(s) from YouTube
    2. Crop signer region
    3. Transcribe audio (WhisperX)
    4. Split into sentence clips
    5. Face clustering (REQUIRED) - identify signers
    6. Create ZIP archive
    """
    
    def __init__(
        self,
        work_dir: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ):
        """
        Initialize the pipeline.
        
        Args:
            work_dir: Working directory for this pipeline run
            progress_callback: Optional callback for progress updates (percent, message)
        """
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.progress_callback = progress_callback
        
        # Sub directories
        self.raw_dir = self.work_dir / "raw"
        self.signer_dir = self.work_dir / "signer_clips"
        self.transcripts_dir = self.work_dir / "transcripts"
        self.clips_dir = self.work_dir / "sentence_clips"
        self.metadata_file = self.work_dir / "sentence_clips_metadata.csv"
        
        # Create directories
        for d in [self.raw_dir, self.signer_dir, self.transcripts_dir, self.clips_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Initialize steps
        self._init_steps()
    
    def _init_steps(self):
        """Initialize all pipeline steps"""
        self.downloader = DownloaderStep(self.work_dir, self.progress_callback)
        self.preprocessor = PreprocessorStep(self.work_dir, self.progress_callback)
        self.transcriber = TranscriberStep(self.work_dir, self.progress_callback)
        self.splitter = SplitterStep(self.work_dir, self.progress_callback)
        self.clusterer = ClustererStep(self.work_dir, self.progress_callback)
        self.archiver = ArchiverStep(self.work_dir, self.progress_callback)
    
    def update_progress(self, percent: int, message: str):
        """Update progress via callback"""
        logger.info(f"[{percent}%] {message}")
        if self.progress_callback:
            self.progress_callback(percent, message)
    
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
        
        Args:
            youtube_url: YouTube video or playlist URL
            max_videos: Maximum number of videos to process
            
        Returns:
            Path to result ZIP file, or None if failed
        """
        self.update_progress(0, "Starting pipeline...")
        
        # Step 1: Download video(s)
        video_paths = self.downloader.run(youtube_url, max_videos)
        if not video_paths:
            logger.error("No videos downloaded")
            return None
        
        total_videos = len(video_paths)
        all_metadata: List[Dict] = []
        
        # Process each video (steps 2-4)
        for idx, video_path in enumerate(video_paths):
            video_num = idx + 1
            base_progress = 15 + int((idx / total_videos) * 55)  # 15-70%
            
            self.update_progress(base_progress, f"Processing video {video_num}/{total_videos}: {video_path.name}")
            
            # Step 2: Crop signer
            self.update_progress(base_progress + 5, f"[{video_num}/{total_videos}] Cropping signer...")
            signer_video = self.preprocessor.run(video_path)
            if not signer_video:
                logger.warning(f"Failed to crop {video_path.name}, skipping...")
                continue
            
            # Step 3: Transcribe
            self.update_progress(base_progress + 15, f"[{video_num}/{total_videos}] Transcribing...")
            transcript_path = self.transcriber.run(signer_video)
            if not transcript_path:
                logger.warning(f"Failed to transcribe {video_path.name}, skipping...")
                continue
            
            # Step 4: Split into clips
            self.update_progress(base_progress + 25, f"[{video_num}/{total_videos}] Splitting clips...")
            metadata = self.splitter.run(signer_video, transcript_path)
            if metadata:
                all_metadata.extend(metadata)
            else:
                logger.warning(f"No clips generated for {video_path.name}")
        
        # Check if we have any clips
        if not all_metadata:
            logger.error("No clips generated from any video")
            return None
        
        # Save combined metadata (before clustering)
        self.update_progress(75, "Saving combined metadata...")
        self._save_combined_metadata(all_metadata)
        
        # Step 5: Face Clustering (REQUIRED)
        try:
            self.clusterer.run()
        except Exception as e:
            logger.error(f"Pipeline failed at face clustering: {e}")
            self.update_progress(100, f"Pipeline failed: Face clustering error - {e}")
            return None
        
        # Step 6: Create ZIP
        zip_path = self.archiver.run()
        
        self.update_progress(100, f"Pipeline complete! Processed {total_videos} video(s), {len(all_metadata)} clips with signer IDs")
        return zip_path
    
    def _save_combined_metadata(self, all_metadata: List[Dict]):
        """Save combined metadata from all videos"""
        fieldnames = [
            'name', 'video_source', 'segment_id', 'start_original', 'start_rounded',
            'end_original', 'end_rounded', 'end_with_buffer', 'duration',
            'is_last_segment', 'text', 'status'
        ]
        
        with open(self.metadata_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_metadata)
    
    def cleanup(self):
        """Clean up work directory"""
        try:
            shutil.rmtree(self.work_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup work directory: {e}")

