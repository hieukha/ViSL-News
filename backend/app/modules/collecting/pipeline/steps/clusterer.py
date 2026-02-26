"""
Step 5: Face clustering - identify and group signers.
"""
import csv
import json
import pickle
import logging
from pathlib import Path
from typing import Dict, Optional, Callable

import numpy as np
from tqdm import tqdm

from .base import PipelineStep
from ..utils.face import (
    INSIGHTFACE_AVAILABLE,
    FACE_DETECTION_METHOD,
    FACE_EMBEDDING_METHOD,
    extract_face_embedding_from_video,
    cluster_embeddings,
)

logger = logging.getLogger(__name__)


class ClustererStep(PipelineStep):
    """
    Step 5: Face clustering to identify signers.
    
    Uses face recognition to:
    - Extract face embeddings from clips
    - Cluster embeddings to identify unique signers
    - Assign signer IDs to each clip
    """
    
    @property
    def name(self) -> str:
        return "Face Clustering"
    
    def __init__(
        self,
        work_dir: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ):
        super().__init__(work_dir, progress_callback)
        self.clips_dir = self.work_dir / "sentence_clips"
        self.metadata_file = self.work_dir / "sentence_clips_metadata.csv"
        self.embeddings_file = self.work_dir / "face_embeddings.pkl"
        self.cluster_results_file = self.work_dir / "cluster_results.json"
    
    def run(self) -> bool:
        """
        Cluster signers using face recognition.
        
        Returns:
            True if successful, False otherwise
        """
        self.update_progress(80, "Starting face clustering (required step)...")
        
        # Check InsightFace availability
        if INSIGHTFACE_AVAILABLE:
            logger.info("Face clustering: Using InsightFace + DBSCAN")
        else:
            logger.error("Face clustering: InsightFace not available!")
            raise Exception("InsightFace is required for face clustering")
        
        # Extract embeddings
        self.update_progress(82, "Extracting face embeddings from clips...")
        embeddings_dict = self._extract_all_embeddings()
        
        if not embeddings_dict:
            logger.error("Face clustering failed: No embeddings extracted from clips")
            raise Exception("Face clustering failed: Could not extract face embeddings from any clips")
        
        logger.info(f"Extracted embeddings from {len(embeddings_dict)} clips")
        
        # Cluster embeddings
        self.update_progress(88, f"Clustering {len(embeddings_dict)} face embeddings...")
        signer_assignments = cluster_embeddings(embeddings_dict)
        
        if not signer_assignments:
            logger.error("Face clustering failed: Clustering returned no results")
            raise Exception("Face clustering failed: No signers identified")
        
        n_signers = len(set(signer_assignments.values()))
        logger.info(f"Identified {n_signers} unique signer(s)")
        
        # Update metadata with signer IDs
        self.update_progress(92, "Updating metadata with signer IDs...")
        self._update_metadata_with_signers(signer_assignments)
        
        # Save cluster results
        self._save_cluster_results(signer_assignments, n_signers)
        
        self.update_progress(95, f"Face clustering complete: {n_signers} signer(s) identified in {len(signer_assignments)} clips")
        return True
    
    def _extract_all_embeddings(self) -> Dict[str, np.ndarray]:
        """Extract face embeddings from all video clips"""
        logger.info(f"\n{'='*60}")
        logger.info("EXTRACTING FACE EMBEDDINGS")
        logger.info(f"{'='*60}")
        
        # Load metadata
        if not self.metadata_file.exists():
            logger.error(f"Metadata file not found: {self.metadata_file}")
            return {}
        
        clip_names = []
        with open(self.metadata_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('status') == 'success':
                    clip_names.append(row['name'])
        
        logger.info(f"Found {len(clip_names)} clips to process")
        logger.info(f"Face detection method: {FACE_DETECTION_METHOD}")
        logger.info(f"Face embedding method: {FACE_EMBEDDING_METHOD}")
        
        embeddings_dict = {}
        successful = 0
        failed = 0
        
        for clip_name in tqdm(clip_names, desc="Extracting embeddings"):
            video_path = self.clips_dir / f"{clip_name}.mp4"
            
            if not video_path.exists():
                logger.warning(f"Video not found: {video_path}")
                failed += 1
                continue
            
            embedding = extract_face_embedding_from_video(
                video_path,
                detection_method=FACE_DETECTION_METHOD,
                embedding_method=FACE_EMBEDDING_METHOD
            )
            
            if embedding is not None:
                embeddings_dict[clip_name] = embedding
                successful += 1
            else:
                failed += 1
        
        # Save embeddings
        if embeddings_dict:
            with open(self.embeddings_file, 'wb') as f:
                pickle.dump(embeddings_dict, f)
            logger.info(f"\n✓ Saved {len(embeddings_dict)} embeddings to {self.embeddings_file}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Extraction complete: ✓ {successful}, ✗ {failed}")
        logger.info(f"{'='*60}\n")
        
        return embeddings_dict
    
    def _update_metadata_with_signers(self, signer_assignments: Dict[str, int]):
        """Update metadata CSV with signer IDs"""
        logger.info(f"\n{'='*60}")
        logger.info("UPDATING METADATA WITH SIGNER IDs")
        logger.info(f"{'='*60}")
        
        if not self.metadata_file.exists():
            logger.error(f"Metadata file not found: {self.metadata_file}")
            return
        
        rows = []
        with open(self.metadata_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames)
            
            # Add signer_id column if not present
            if 'signer_id' not in fieldnames:
                fieldnames.append('signer_id')
            
            for row in reader:
                clip_name = row.get('name', '')
                signer_id = signer_assignments.get(clip_name, -1)
                row['signer_id'] = signer_id
                rows.append(row)
        
        # Write updated metadata
        with open(self.metadata_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        # Log signer distribution
        signer_counts = {}
        for row in rows:
            signer_id = row.get('signer_id', -1)
            if signer_id != -1:
                signer_counts[signer_id] = signer_counts.get(signer_id, 0) + 1
        
        logger.info(f"✓ Updated metadata saved")
        logger.info(f"  Total clips: {len(rows)}")
        logger.info(f"  Clips with signer IDs: {sum(1 for r in rows if r.get('signer_id', -1) != -1)}")
        logger.info(f"  Signer distribution: {signer_counts}")
        logger.info(f"{'='*60}\n")
    
    def _save_cluster_results(self, signer_assignments: Dict[str, int], n_signers: int):
        """Save clustering results to JSON"""
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
        
        with open(self.cluster_results_file, 'w', encoding='utf-8') as f:
            json.dump(cluster_results, f, ensure_ascii=False, indent=2)

