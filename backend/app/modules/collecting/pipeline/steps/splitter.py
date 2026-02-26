"""
Step 4: Split video into sentence clips based on transcript.
"""
import csv
import json
import math
import logging
from pathlib import Path
from typing import List, Dict, Optional, Callable

from .base import PipelineStep
from ..utils.video import get_video_duration, cut_video_segment

logger = logging.getLogger(__name__)


class SplitterStep(PipelineStep):
    """
    Step 4: Split video into sentence clips.
    
    Uses transcript segments to cut the video into
    individual sentence clips with metadata.
    """
    
    @property
    def name(self) -> str:
        return "Split Clips"
    
    def __init__(
        self,
        work_dir: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ):
        super().__init__(work_dir, progress_callback)
        self.clips_dir = self.ensure_dir(self.work_dir / "sentence_clips")
        self.metadata_file = self.work_dir / "sentence_clips_metadata.csv"
    
    def run(self, video_path: Path, transcript_path: Path) -> List[Dict]:
        """
        Split video into sentence clips based on transcript.
        
        Args:
            video_path: Path to video file
            transcript_path: Path to transcript JSON file
            
        Returns:
            List of metadata dictionaries for each clip
        """
        self.update_progress(70, "Splitting into sentence clips...")
        
        metadata_list = []
        
        try:
            # Load transcript
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript = json.load(f)
            
            segments = transcript.get('segments', [])
            if not segments:
                logger.warning("No segments found in transcript")
                return []
            
            # Get video duration
            video_duration = get_video_duration(video_path)
            if not video_duration:
                video_duration = 9999
            
            # Get base name for clips
            base_name = video_path.stem
            if base_name.startswith('signer_'):
                base_name = base_name[7:]
            
            end_buffer = 2.0
            total_segments = len(segments)
            
            for idx, segment in enumerate(segments):
                start_original = segment.get('start', 0)
                end_original = segment.get('end', 0)
                text = segment.get('text', '').strip()
                
                # Round timestamps
                start = math.ceil(start_original)
                end_rounded = math.ceil(end_original)
                
                # Add buffer for non-last segments
                is_last = (idx == total_segments - 1)
                end_with_buffer = min(end_rounded + (0 if is_last else end_buffer), video_duration)
                
                # Skip invalid segments
                if end_rounded <= start or start < 0:
                    continue
                
                # Generate output path
                output_filename = f"{base_name}-{idx}.mp4"
                output_path = self.clips_dir / output_filename
                
                # Cut clip
                duration = end_with_buffer - start
                success = cut_video_segment(
                    input_path=video_path,
                    output_path=output_path,
                    start_time=start,
                    duration=duration,
                    preset='fast',
                    crf=23
                )
                
                status = 'success' if success else 'failed'
                
                # Record metadata
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
            self._save_metadata(metadata_list)
            
            return metadata_list
            
        except Exception as e:
            logger.error(f"Error splitting clips: {e}")
            return []
    
    def _save_metadata(self, metadata_list: List[Dict]):
        """Save metadata to CSV file"""
        self.update_progress(85, "Saving metadata...")
        
        fieldnames = [
            'name', 'video_source', 'segment_id', 'start_original', 'start_rounded',
            'end_original', 'end_rounded', 'end_with_buffer', 'duration',
            'is_last_segment', 'text', 'status'
        ]
        
        with open(self.metadata_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(metadata_list)
    
    def save_combined_metadata(self, all_metadata: List[Dict]):
        """Save combined metadata from multiple videos"""
        self._save_metadata(all_metadata)

