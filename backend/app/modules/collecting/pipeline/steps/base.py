"""
Abstract base class for pipeline steps.
All pipeline steps should inherit from this class.
"""
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class PipelineStep(ABC):
    """
    Abstract base class for all pipeline steps.
    
    Each step represents a distinct stage in the video processing pipeline.
    Steps are executed sequentially by the orchestrator.
    """
    
    def __init__(
        self,
        work_dir: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ):
        """
        Initialize the pipeline step.
        
        Args:
            work_dir: Working directory for this pipeline run
            progress_callback: Optional callback for progress updates (percent, message)
        """
        self.work_dir = Path(work_dir)
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this step"""
        pass
    
    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """
        Execute this pipeline step.
        
        Returns:
            Step-specific output (e.g., file paths, metadata)
        """
        pass
    
    def update_progress(self, percent: int, message: str):
        """
        Update progress via callback.
        
        Args:
            percent: Progress percentage (0-100)
            message: Progress message
        """
        self.logger.info(f"[{percent}%] {message}")
        if self.progress_callback:
            self.progress_callback(percent, message)
    
    def ensure_dir(self, dir_path: Path) -> Path:
        """
        Ensure a directory exists, create if necessary.
        
        Args:
            dir_path: Directory path
            
        Returns:
            The directory path
        """
        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

