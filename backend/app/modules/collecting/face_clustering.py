#!/usr/bin/env python3
"""
Face Clustering Module for ViSL Tool
Clusters signers using face recognition and clustering algorithms.
Extracts face embeddings from video clips and clusters them to identify different signers.

Based on: https://github.com/hamidsadeghi68/face-clustering
"""
import cv2
import numpy as np
import csv
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

from tqdm import tqdm

logger = logging.getLogger(__name__)

# Try to import face recognition libraries
# Priority: InsightFace > face_recognition > OpenCV

# InsightFace (best accuracy - recommended by repository)
try:
    import insightface
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    INSIGHTFACE_AVAILABLE = False
    logger.warning("InsightFace not available. Install: pip install insightface onnxruntime")

# MTCNN for face detection (better than Haar Cascade)
try:
    from mtcnn import MTCNN
    MTCNN_AVAILABLE = True
except ImportError:
    MTCNN_AVAILABLE = False

# face_recognition library (fallback)
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

try:
    from sklearn.cluster import DBSCAN, KMeans, AgglomerativeClustering
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.error("scikit-learn not available. Please install: pip install scikit-learn")


# Configuration
FRAMES_PER_VIDEO = 10  # Number of frames to extract per video for face detection

# Face detection methods: "insightface" (best), "mtcnn", "face_recognition", "opencv_haar"
FACE_DETECTION_METHOD = "insightface" if INSIGHTFACE_AVAILABLE else ("mtcnn" if MTCNN_AVAILABLE else ("face_recognition" if FACE_RECOGNITION_AVAILABLE else "opencv_haar"))

# Face embedding methods: "insightface" (best), "face_recognition", "opencv"
FACE_EMBEDDING_METHOD = "insightface" if INSIGHTFACE_AVAILABLE else ("face_recognition" if FACE_RECOGNITION_AVAILABLE else "opencv")

# Clustering method: "dbscan", "kmeans", "agglomerative"
CLUSTERING_METHOD = "dbscan"

# Clustering parameters (following original repository)
DBSCAN_EPS = 1.0  # For normalized embeddings, distance range is [0, 2]
DBSCAN_MIN_SAMPLES = 2  # Minimum number of samples in a neighborhood
KMEANS_N_CLUSTERS = None  # None = auto-detect, or specify number of signers
AGGLOMERATIVE_N_CLUSTERS = None  # None = auto-detect


# Global models (initialized once)
_insightface_model = None
_mtcnn_detector = None


def get_insightface_model():
    """Get or initialize InsightFace model (singleton)"""
    global _insightface_model
    if _insightface_model is None and INSIGHTFACE_AVAILABLE:
        try:
            # Try to load a pre-trained model (buffalo_l is recommended)
            # Try GPU first, fallback to CPU if not available
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            _insightface_model = insightface.app.FaceAnalysis(
                name='buffalo_l',  # or 'buffalo_s' for smaller model
                providers=providers
            )
            _insightface_model.prepare(ctx_id=0, det_size=(640, 640))
            logger.info("✓ InsightFace model loaded")
        except Exception as e:
            logger.warning(f"Failed to load InsightFace model: {e}")
            _insightface_model = False  # Mark as failed
    return _insightface_model if _insightface_model is not False else None


def get_mtcnn_detector():
    """Get or initialize MTCNN detector (singleton)"""
    global _mtcnn_detector
    if _mtcnn_detector is None and MTCNN_AVAILABLE:
        try:
            _mtcnn_detector = MTCNN()
            logger.info("✓ MTCNN detector loaded")
        except Exception as e:
            logger.warning(f"Failed to load MTCNN: {e}")
            _mtcnn_detector = False
    return _mtcnn_detector if _mtcnn_detector is not False else None


def extract_frames_from_video(video_path: Path, num_frames: int = FRAMES_PER_VIDEO) -> List[np.ndarray]:
    """
    Extract frames from video at evenly spaced intervals.
    
    Args:
        video_path: Path to video file
        num_frames: Number of frames to extract
        
    Returns:
        List of frames (BGR format)
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error(f"Cannot open video: {video_path}")
        return []
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0
    
    if total_frames == 0:
        logger.warning(f"Video has no frames: {video_path}")
        cap.release()
        return []
    
    # Calculate frame indices to extract
    if num_frames >= total_frames:
        frame_indices = list(range(total_frames))
    else:
        # Extract frames at evenly spaced intervals
        step = total_frames / (num_frames + 1)
        frame_indices = [int(step * (i + 1)) for i in range(num_frames)]
    
    frames = []
    for frame_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if ret and frame is not None:
            frames.append(frame)
    
    cap.release()
    return frames


def detect_face_insightface(frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect face using InsightFace (includes detection and alignment).
    
    Args:
        frame: Input frame (BGR)
        
    Returns:
        (x, y, w, h) bounding box or None
    """
    model = get_insightface_model()
    if model is None:
        return None
    
    try:
        # InsightFace expects BGR format
        faces = model.get(frame)
        
        if len(faces) > 0:
            # Return the largest face
            largest_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            bbox = largest_face.bbox.astype(int)
            x, y, x2, y2 = bbox
            w, h = x2 - x, y2 - y
            return (x, y, w, h)
    except Exception as e:
        logger.debug(f"InsightFace detection error: {e}")
    
    return None


def detect_face_mtcnn(frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect face using MTCNN (better than Haar Cascade).
    
    Args:
        frame: Input frame (BGR)
        
    Returns:
        (x, y, w, h) bounding box or None
    """
    detector = get_mtcnn_detector()
    if detector is None:
        return None
    
    try:
        # MTCNN expects RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = detector.detect_faces(rgb_frame)
        
        if len(results) > 0:
            # Return the largest face
            largest_face = max(results, key=lambda r: r['box'][2] * r['box'][3])
            x, y, w, h = largest_face['box']
            return (x, y, w, h)
    except Exception as e:
        logger.debug(f"MTCNN detection error: {e}")
    
    return None


def detect_face_opencv_haar(frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect face using OpenCV Haar Cascade.
    
    Args:
        frame: Input frame (BGR)
        
    Returns:
        (x, y, w, h) bounding box or None
    """
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Load Haar Cascade classifier
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    if face_cascade.empty():
        logger.error("Failed to load Haar Cascade classifier")
        return None
    
    # Detect faces
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )
    
    if len(faces) > 0:
        # Return the largest face
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest_face
        return (x, y, w, h)
    
    return None


def detect_face_face_recognition(frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect face using face_recognition library.
    
    Args:
        frame: Input frame (BGR)
        
    Returns:
        (x, y, w, h) bounding box or None
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return None
    
    # Convert BGR to RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Detect faces
    face_locations = face_recognition.face_locations(rgb_frame, model="hog")
    
    if len(face_locations) > 0:
        # Return the largest face
        largest_face = max(face_locations, key=lambda loc: (loc[2] - loc[0]) * (loc[3] - loc[1]))
        top, right, bottom, left = largest_face
        x, y, w, h = left, top, right - left, bottom - top
        return (x, y, w, h)
    
    return None


def extract_face_embedding_insightface(frame: np.ndarray, face_box: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
    """
    Extract face embedding using InsightFace (best accuracy - 512 dimensions).
    This is the recommended method from the repository.
    
    Args:
        frame: Input frame (BGR)
        face_box: Optional face bounding box (x, y, w, h) - if None, will detect automatically
        
    Returns:
        Face embedding vector (512 dimensions) or None
    """
    model = get_insightface_model()
    if model is None:
        return None
    
    try:
        # InsightFace can detect and extract in one step
        faces = model.get(frame)
        
        if len(faces) > 0:
            # Use the largest face
            largest_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            # Get normalized embedding (512 dimensions)
            embedding = largest_face.normed_embedding
            return embedding
    except Exception as e:
        logger.debug(f"InsightFace embedding error: {e}")
    
    return None


def extract_face_embedding_face_recognition(frame: np.ndarray, face_box: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
    """
    Extract face embedding using face_recognition library.
    
    Args:
        frame: Input frame (BGR)
        face_box: Optional face bounding box (x, y, w, h)
        
    Returns:
        Face embedding vector (128 dimensions) or None
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return None
    
    # Convert BGR to RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # If face box provided, extract face region
    if face_box:
        x, y, w, h = face_box
        face_image = rgb_frame[y:y+h, x:x+w]
        if face_image.size == 0:
            return None
    else:
        face_image = rgb_frame
    
    # Extract embeddings
    encodings = face_recognition.face_encodings(face_image)
    
    if len(encodings) > 0:
        return encodings[0]  # Return first encoding
    
    return None


def extract_face_embedding_opencv(frame: np.ndarray, face_box: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
    """
    Extract face embedding using OpenCV (simpler approach - uses face region as features).
    This is a fallback method when face_recognition is not available.
    
    Args:
        frame: Input frame (BGR)
        face_box: Face bounding box (x, y, w, h)
        
    Returns:
        Face embedding vector (resized face image flattened) or None
    """
    if face_box is None:
        # Try to detect face first
        face_box = detect_face_opencv_haar(frame)
        if face_box is None:
            return None
    
    x, y, w, h = face_box
    
    # Extract face region
    face_roi = frame[y:y+h, x:x+w]
    
    if face_roi.size == 0:
        return None
    
    # Resize to fixed size for consistency
    face_resized = cv2.resize(face_roi, (64, 64))
    
    # Convert to grayscale and normalize
    gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
    normalized = gray.astype(np.float32) / 255.0
    
    # Flatten to create embedding vector
    embedding = normalized.flatten()
    
    return embedding


def extract_face_embedding_from_video(
    video_path: Path, 
    detection_method: str = FACE_DETECTION_METHOD,
    embedding_method: str = FACE_EMBEDDING_METHOD
) -> Optional[np.ndarray]:
    """
    Extract face embedding from a video by selecting the best quality frame.
    Uses face detection confidence score to select the best frame.
    
    Args:
        video_path: Path to video file
        detection_method: Face detection method ("insightface", "mtcnn", "face_recognition", "opencv_haar")
        embedding_method: Face embedding method ("insightface", "face_recognition", "opencv")
        
    Returns:
        Face embedding from the best quality frame, or None
    """
    frames = extract_frames_from_video(video_path, FRAMES_PER_VIDEO)
    
    if not frames:
        return None
    
    best_embedding = None
    best_score = -1.0
    
    for frame in frames:
        # Priority: InsightFace (best) > face_recognition > OpenCV
        if embedding_method == "insightface" and INSIGHTFACE_AVAILABLE:
            model = get_insightface_model()
            if model is not None:
                try:
                    faces = model.get(frame)
                    if len(faces) > 0:
                        # Get the largest face
                        largest_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                        # Use detection score as quality metric
                        score = float(largest_face.det_score)
                        if score > best_score:
                            best_score = score
                            best_embedding = largest_face.normed_embedding
                except Exception as e:
                    logger.debug(f"InsightFace embedding error: {e}")
        
        elif embedding_method == "face_recognition" and FACE_RECOGNITION_AVAILABLE:
            # Detect face first
            if detection_method == "mtcnn" and MTCNN_AVAILABLE:
                face_box = detect_face_mtcnn(frame)
            elif detection_method == "insightface" and INSIGHTFACE_AVAILABLE:
                face_box = detect_face_insightface(frame)
            elif detection_method == "face_recognition":
                face_box = detect_face_face_recognition(frame)
            else:
                face_box = detect_face_opencv_haar(frame)
            
            if face_box:
                embedding = extract_face_embedding_face_recognition(frame, face_box)
                if embedding is not None:
                    # For face_recognition, use face area as quality proxy
                    x, y, w, h = face_box
                    score = float(w * h)  # Larger face = better quality
                    if score > best_score:
                        best_score = score
                        best_embedding = embedding
        
        else:
            # Fallback to OpenCV
            face_box = None
            if detection_method == "mtcnn" and MTCNN_AVAILABLE:
                face_box = detect_face_mtcnn(frame)
            elif detection_method == "insightface" and INSIGHTFACE_AVAILABLE:
                face_box = detect_face_insightface(frame)
            elif detection_method == "face_recognition" and FACE_RECOGNITION_AVAILABLE:
                face_box = detect_face_face_recognition(frame)
            else:
                face_box = detect_face_opencv_haar(frame)
            
            if face_box:
                embedding = extract_face_embedding_opencv(frame, face_box)
                if embedding is not None:
                    x, y, w, h = face_box
                    score = float(w * h)
                    if score > best_score:
                        best_score = score
                        best_embedding = embedding
    
    if best_embedding is None:
        logger.warning(f"No face embeddings extracted from {video_path.name}")
    else:
        logger.debug(f"Best face score: {best_score:.3f} from {video_path.name}")
    
    return best_embedding


def extract_all_embeddings(
    clips_dir: Path,
    metadata_file: Path,
    embeddings_file: Path,
    max_clips: Optional[int] = None
) -> Dict[str, np.ndarray]:
    """
    Extract face embeddings from all video clips.
    
    Args:
        clips_dir: Directory containing sentence clip videos
        metadata_file: Path to metadata CSV
        embeddings_file: Path to save embeddings pickle file
        max_clips: Maximum number of clips to process (None for all)
        
    Returns:
        Dictionary mapping clip names to embeddings
    """
    logger.info(f"\n{'='*60}")
    logger.info("EXTRACTING FACE EMBEDDINGS")
    logger.info(f"{'='*60}")
    
    # Load metadata
    if not metadata_file.exists():
        logger.error(f"Metadata file not found: {metadata_file}")
        return {}
    
    clip_names = []
    with open(metadata_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('status') == 'success':
                clip_names.append(row['name'])
    
    if max_clips:
        clip_names = clip_names[:max_clips]
    
    logger.info(f"Found {len(clip_names)} clips to process")
    logger.info(f"Face detection method: {FACE_DETECTION_METHOD}")
    logger.info(f"Face embedding method: {FACE_EMBEDDING_METHOD}")
    logger.info(f"Frames per video: {FRAMES_PER_VIDEO}")
    
    # Log available methods
    available_methods = []
    if INSIGHTFACE_AVAILABLE:
        available_methods.append("InsightFace ✓")
    if MTCNN_AVAILABLE:
        available_methods.append("MTCNN ✓")
    if FACE_RECOGNITION_AVAILABLE:
        available_methods.append("face_recognition ✓")
    if available_methods:
        logger.info(f"Available methods: {', '.join(available_methods)}")
    else:
        logger.warning("Only basic OpenCV methods available. Consider installing InsightFace for better accuracy.")
    
    logger.info(f"{'='*60}\n")
    
    embeddings_dict = {}
    successful = 0
    failed = 0
    
    for clip_name in tqdm(clip_names, desc="Extracting embeddings"):
        video_path = clips_dir / f"{clip_name}.mp4"
        
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
        with open(embeddings_file, 'wb') as f:
            pickle.dump(embeddings_dict, f)
        logger.info(f"\n✓ Saved {len(embeddings_dict)} embeddings to {embeddings_file}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Extraction complete: ✓ {successful}, ✗ {failed}")
    logger.info(f"{'='*60}\n")
    
    return embeddings_dict


def cluster_embeddings(
    embeddings_dict: Dict[str, np.ndarray],
    method: str = CLUSTERING_METHOD,
    n_clusters: Optional[int] = None
) -> Dict[str, int]:
    """
    Cluster face embeddings to identify different signers.
    Following the original repository approach: NO StandardScaler, NO PCA.
    
    Args:
        embeddings_dict: Dictionary mapping clip names to embeddings
        method: Clustering method ("dbscan", "kmeans", "agglomerative")
        n_clusters: Number of clusters (for kmeans/agglomerative, None for auto)
        
    Returns:
        Dictionary mapping clip names to cluster IDs (signer IDs)
    """
    if not SKLEARN_AVAILABLE:
        logger.error("scikit-learn not available. Cannot perform clustering.")
        return {}
    
    if not embeddings_dict:
        logger.error("No embeddings to cluster")
        return {}
    
    logger.info(f"\n{'='*60}")
    logger.info("CLUSTERING FACE EMBEDDINGS")
    logger.info(f"{'='*60}")
    logger.info(f"Method: {method}")
    logger.info(f"Total embeddings: {len(embeddings_dict)}")
    
    # Prepare data - NO preprocessing (following original repository)
    # InsightFace normed_embedding is already L2 normalized
    clip_names = list(embeddings_dict.keys())
    embeddings = np.array([embeddings_dict[name] for name in clip_names])
    
    logger.info(f"Embedding dimensions: {embeddings.shape[1]}")
    logger.info("Using raw normalized embeddings (no StandardScaler, no PCA)")
    
    # Perform clustering
    if method == "dbscan":
        logger.info(f"DBSCAN parameters: eps={DBSCAN_EPS}, min_samples={DBSCAN_MIN_SAMPLES}")
        # Use euclidean metric (default) - works well with L2 normalized embeddings
        clusterer = DBSCAN(eps=DBSCAN_EPS, min_samples=DBSCAN_MIN_SAMPLES)
        labels = clusterer.fit_predict(embeddings)
        
        # Handle noise points (label = -1)
        n_noise = np.sum(labels == -1)
        if n_noise > 0:
            logger.warning(f"Found {n_noise} noise points (outliers)")
            # Assign noise points to new clusters
            max_label = np.max(labels)
            noise_indices = np.where(labels == -1)[0]
            for i, idx in enumerate(noise_indices):
                labels[idx] = max_label + 1 + i
        
    elif method == "kmeans":
        if n_clusters is None:
            # Estimate number of clusters (simple heuristic: sqrt of n_samples / 2)
            n_clusters = max(2, int(np.sqrt(len(embeddings) / 2)))
            logger.info(f"Auto-detected {n_clusters} clusters")
        
        logger.info(f"K-Means with {n_clusters} clusters")
        clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = clusterer.fit_predict(embeddings)
        
    elif method == "agglomerative":
        if n_clusters is None:
            n_clusters = max(2, int(np.sqrt(len(embeddings) / 2)))
            logger.info(f"Auto-detected {n_clusters} clusters")
        
        logger.info(f"Agglomerative clustering with {n_clusters} clusters")
        clusterer = AgglomerativeClustering(n_clusters=n_clusters, linkage='ward')
        labels = clusterer.fit_predict(embeddings)
        
    else:
        logger.error(f"Unknown clustering method: {method}")
        return {}
    
    # Create result dictionary
    result = {clip_names[i]: int(labels[i]) for i in range(len(clip_names))}
    
    # Count clusters
    unique_labels = np.unique(labels)
    n_clusters_found = len(unique_labels)
    cluster_sizes = {int(label): int(np.sum(labels == label)) for label in unique_labels}
    
    logger.info(f"\n✓ Clustering complete")
    logger.info(f"  Found {n_clusters_found} clusters (signers)")
    logger.info(f"  Cluster sizes: {cluster_sizes}")
    logger.info(f"{'='*60}\n")
    
    return result


def update_metadata_with_signers(
    metadata_file: Path,
    output_file: Path,
    signer_assignments: Dict[str, int]
):
    """
    Update metadata CSV with signer IDs.
    
    Args:
        metadata_file: Input metadata CSV
        output_file: Output metadata CSV with signer IDs
        signer_assignments: Dictionary mapping clip names to signer IDs
    """
    logger.info(f"\n{'='*60}")
    logger.info("UPDATING METADATA WITH SIGNER IDs")
    logger.info(f"{'='*60}")
    
    if not metadata_file.exists():
        logger.error(f"Metadata file not found: {metadata_file}")
        return
    
    rows = []
    with open(metadata_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        
        # Add signer_id column if not present
        if 'signer_id' not in fieldnames:
            fieldnames.append('signer_id')
        
        for row in reader:
            clip_name = row.get('name', '')
            signer_id = signer_assignments.get(clip_name, -1)  # -1 for unknown
            row['signer_id'] = signer_id
            rows.append(row)
    
    # Write updated metadata
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    # Count signers
    signer_counts = {}
    for row in rows:
        signer_id = row.get('signer_id', -1)
        if signer_id != -1:
            signer_counts[signer_id] = signer_counts.get(signer_id, 0) + 1
    
    logger.info(f"✓ Updated metadata saved to: {output_file}")
    logger.info(f"  Total clips: {len(rows)}")
    logger.info(f"  Clips with signer IDs: {sum(1 for r in rows if r.get('signer_id', -1) != -1)}")
    logger.info(f"  Signer distribution: {signer_counts}")
    logger.info(f"{'='*60}\n")


def save_cluster_results(
    signer_assignments: Dict[str, int],
    output_file: Path
):
    """
    Save clustering results to JSON file.
    
    Args:
        signer_assignments: Dictionary mapping clip names to signer IDs
        output_file: Output JSON file path
    """
    import json
    
    # Group clips by signer
    signer_groups = {}
    for clip_name, signer_id in signer_assignments.items():
        if signer_id not in signer_groups:
            signer_groups[signer_id] = []
        signer_groups[signer_id].append(clip_name)
    
    results = {
        'total_clips': len(signer_assignments),
        'n_signers': len(signer_groups),
        'signer_groups': signer_groups,
        'clustering_method': CLUSTERING_METHOD,
        'face_detection_method': FACE_DETECTION_METHOD,
        'face_embedding_method': FACE_EMBEDDING_METHOD
    }
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✓ Cluster results saved to: {output_file}")
