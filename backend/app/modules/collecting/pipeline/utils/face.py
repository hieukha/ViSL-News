"""
Face detection and recognition utilities.
Provides GPU-accelerated face detection using InsightFace with Haar Cascade fallback.
"""
import logging
from typing import Optional, Tuple, List, Dict

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Try to import InsightFace for GPU-accelerated face detection
try:
    import insightface
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    INSIGHTFACE_AVAILABLE = False
    logger.warning("InsightFace not available. Install: pip install insightface onnxruntime")

# Try to import MTCNN for face detection
try:
    from mtcnn import MTCNN
    MTCNN_AVAILABLE = True
except ImportError:
    MTCNN_AVAILABLE = False

# Try to import face_recognition library
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

# Try to import sklearn for clustering
try:
    from sklearn.cluster import DBSCAN, KMeans, AgglomerativeClustering
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.error("scikit-learn not available. Please install: pip install scikit-learn")

# Detection config for signer check
ROI_CONFIG = {'x': 125, 'y': 637, 'width': 178, 'height': 159}
TEST_TIMESTAMPS = [2, 10, 20]

# Face detection for signer check (Haar Cascade as fallback)
FACE_XML = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
FACE_CLF = cv2.CascadeClassifier(FACE_XML)

# Configuration
FRAMES_PER_VIDEO = 10  # Number of frames to extract per video for face detection

# Face detection methods
FACE_DETECTION_METHOD = "insightface" if INSIGHTFACE_AVAILABLE else (
    "mtcnn" if MTCNN_AVAILABLE else (
        "face_recognition" if FACE_RECOGNITION_AVAILABLE else "opencv_haar"
    )
)

# Face embedding methods
FACE_EMBEDDING_METHOD = "insightface" if INSIGHTFACE_AVAILABLE else (
    "face_recognition" if FACE_RECOGNITION_AVAILABLE else "opencv"
)

# Clustering method and parameters
CLUSTERING_METHOD = "dbscan"
DBSCAN_EPS = 1.0
DBSCAN_MIN_SAMPLES = 2
KMEANS_N_CLUSTERS = None
AGGLOMERATIVE_N_CLUSTERS = None

# =========================
# Global models (singleton pattern)
# =========================
_insightface_model = None
_mtcnn_detector = None


def get_insightface_model():
    """Get or initialize InsightFace model (singleton pattern)"""
    global _insightface_model
    if _insightface_model is None and INSIGHTFACE_AVAILABLE:
        try:
            # Try GPU first (CUDA), fallback to CPU
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            _insightface_model = insightface.app.FaceAnalysis(
                name='buffalo_l',  # High accuracy model
                providers=providers
            )
            _insightface_model.prepare(ctx_id=0, det_size=(640, 640))
            logger.info("✓ InsightFace model loaded (GPU accelerated)")
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


def detect_face_insightface(img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect face using InsightFace (GPU accelerated).
    
    Args:
        img: Input image (BGR format)
        
    Returns:
        (x, y, w, h) bounding box of the largest face, or None if no face detected
    """
    model = get_insightface_model()
    if model is None:
        return None
    
    try:
        # InsightFace expects BGR format (same as OpenCV)
        faces = model.get(img)
        
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


def detect_face_haar(img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Fallback face detection using OpenCV Haar Cascade.
    
    Args:
        img: Input image (BGR format)
        
    Returns:
        (x, y, w, h) bounding box of the largest face, or None if no face detected
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    
    faces = FACE_CLF.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=6,
        minSize=(40, 40),
    )
    
    if len(faces) > 0:
        # Return the largest face
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest_face
        return (x, y, w, h)
    
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


def has_person(img: np.ndarray) -> bool:
    """
    Check if a person (face) is present in the image.
    Uses InsightFace (GPU) if available, falls back to Haar Cascade.
    
    Args:
        img: Input image (BGR format)
        
    Returns:
        True if a face is detected, False otherwise
    """
    # Try InsightFace first (better accuracy, GPU accelerated)
    if INSIGHTFACE_AVAILABLE:
        face_box = detect_face_insightface(img)
        if face_box is not None:
            return True
    
    # Fallback to Haar Cascade if InsightFace fails or not available
    face_box = detect_face_haar(img)
    return face_box is not None


def extract_frame_at_timestamp(video_path: str, timestamp: float) -> Optional[np.ndarray]:
    """Extract a single frame from video at given timestamp"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_number = int(timestamp * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def extract_frames_from_video(video_path, num_frames: int = FRAMES_PER_VIDEO) -> List[np.ndarray]:
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


# =========================
# Face Embedding Functions
# =========================

def extract_face_embedding_insightface(frame: np.ndarray, face_box: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
    """
    Extract face embedding using InsightFace (best accuracy - 512 dimensions).
    
    Args:
        frame: Input frame (BGR)
        face_box: Optional face bounding box (x, y, w, h)
        
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
        return encodings[0]
    
    return None


def extract_face_embedding_opencv(frame: np.ndarray, face_box: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
    """
    Extract face embedding using OpenCV (fallback method).
    
    Args:
        frame: Input frame (BGR)
        face_box: Face bounding box (x, y, w, h)
        
    Returns:
        Face embedding vector or None
    """
    if face_box is None:
        face_box = detect_face_haar(frame)
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
    video_path,
    detection_method: str = FACE_DETECTION_METHOD,
    embedding_method: str = FACE_EMBEDDING_METHOD
) -> Optional[np.ndarray]:
    """
    Extract face embedding from a video by selecting the best quality frame.
    
    Args:
        video_path: Path to video file
        detection_method: Face detection method
        embedding_method: Face embedding method
        
    Returns:
        Face embedding from the best quality frame, or None
    """
    frames = extract_frames_from_video(video_path, FRAMES_PER_VIDEO)
    
    if not frames:
        return None
    
    best_embedding = None
    best_score = -1.0
    
    for frame in frames:
        if embedding_method == "insightface" and INSIGHTFACE_AVAILABLE:
            model = get_insightface_model()
            if model is not None:
                try:
                    faces = model.get(frame)
                    if len(faces) > 0:
                        largest_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                        score = float(largest_face.det_score)
                        if score > best_score:
                            best_score = score
                            best_embedding = largest_face.normed_embedding
                except Exception as e:
                    logger.debug(f"InsightFace embedding error: {e}")
        
        elif embedding_method == "face_recognition" and FACE_RECOGNITION_AVAILABLE:
            if detection_method == "mtcnn" and MTCNN_AVAILABLE:
                face_box = detect_face_mtcnn(frame)
            elif detection_method == "insightface" and INSIGHTFACE_AVAILABLE:
                face_box = detect_face_insightface(frame)
            elif detection_method == "face_recognition":
                face_box = detect_face_face_recognition(frame)
            else:
                face_box = detect_face_haar(frame)
            
            if face_box:
                embedding = extract_face_embedding_face_recognition(frame, face_box)
                if embedding is not None:
                    x, y, w, h = face_box
                    score = float(w * h)
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
                face_box = detect_face_haar(frame)
            
            if face_box:
                embedding = extract_face_embedding_opencv(frame, face_box)
                if embedding is not None:
                    x, y, w, h = face_box
                    score = float(w * h)
                    if score > best_score:
                        best_score = score
                        best_embedding = embedding
    
    if best_embedding is None:
        logger.warning(f"No face embeddings extracted from {video_path}")
    else:
        logger.debug(f"Best face score: {best_score:.3f} from {video_path}")
    
    return best_embedding


# =========================
# Clustering Functions
# =========================

def cluster_embeddings(
    embeddings_dict: Dict[str, np.ndarray],
    method: str = CLUSTERING_METHOD,
    n_clusters: Optional[int] = None
) -> Dict[str, int]:
    """
    Cluster face embeddings to identify different signers.
    
    Args:
        embeddings_dict: Dictionary mapping clip names to embeddings
        method: Clustering method ("dbscan", "kmeans", "agglomerative")
        n_clusters: Number of clusters (for kmeans/agglomerative)
        
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
    
    # Prepare data
    clip_names = list(embeddings_dict.keys())
    embeddings = np.array([embeddings_dict[name] for name in clip_names])
    
    logger.info(f"Embedding dimensions: {embeddings.shape[1]}")
    logger.info("Using raw normalized embeddings (no StandardScaler, no PCA)")
    
    # Perform clustering
    if method == "dbscan":
        logger.info(f"DBSCAN parameters: eps={DBSCAN_EPS}, min_samples={DBSCAN_MIN_SAMPLES}")
        clusterer = DBSCAN(eps=DBSCAN_EPS, min_samples=DBSCAN_MIN_SAMPLES)
        labels = clusterer.fit_predict(embeddings)
        
        # Handle noise points (label = -1)
        n_noise = np.sum(labels == -1)
        if n_noise > 0:
            logger.warning(f"Found {n_noise} noise points (outliers)")
            max_label = np.max(labels)
            noise_indices = np.where(labels == -1)[0]
            for i, idx in enumerate(noise_indices):
                labels[idx] = max_label + 1 + i
        
    elif method == "kmeans":
        if n_clusters is None:
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

