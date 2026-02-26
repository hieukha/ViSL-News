"""
Step 3: Transcribe video using WhisperX.
"""
import json
import logging
from pathlib import Path
from typing import Optional, Callable

from .base import PipelineStep

logger = logging.getLogger(__name__)


class TranscriberStep(PipelineStep):
    """
    Step 3: Transcribe video audio using WhisperX.
    
    Uses WhisperX for:
    - Speech-to-text transcription
    - Word-level timestamp alignment
    - Vietnamese language support
    """
    
    @property
    def name(self) -> str:
        return "Transcribe Audio"
    
    def __init__(
        self,
        work_dir: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ):
        super().__init__(work_dir, progress_callback)
        self.transcripts_dir = self.ensure_dir(self.work_dir / "transcripts")
    
    def run(self, video_path: Path) -> Optional[Path]:
        """
        Transcribe video using WhisperX.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Path to transcript JSON file, or None if failed
        """
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
            
            # Align timestamps
            self.update_progress(55, "Aligning timestamps...")
            try:
                align_model, metadata = whisperx.load_align_model(language_code="vi", device=device)
                result = whisperx.align(
                    result["segments"],
                    align_model,
                    metadata,
                    audio,
                    device,
                    return_char_alignments=False
                )
            except Exception as e:
                logger.warning(f"Could not load alignment model: {e}, using raw transcription")
            
            # Generate output filename
            video_name = video_path.stem
            if video_name.startswith("signer_"):
                video_name = video_name[7:]
            
            output_file = self.transcripts_dir / f"{video_name}.json"
            
            # Save transcript
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            # Cleanup GPU memory
            del model, audio
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            segment_count = len(result.get('segments', []))
            self.update_progress(65, f"Transcribed: {segment_count} segments")
            return output_file
            
        except Exception as e:
            logger.error(f"Error transcribing: {e}")
            return None

