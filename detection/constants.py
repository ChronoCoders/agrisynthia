"""
Shared constants for the detection application.

This module contains all configuration constants used across the detection
and dron_map applications to ensure consistency and prevent duplication.
"""

from pathlib import Path
from typing import Dict

# Base directory for the project
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# MODEL CONFIGURATION
# ==============================================================================

# Fruit model weights (average weight per fruit in kg)
FRUIT_WEIGHTS: Dict[str, float] = {
    "mandalina": 0.125,  # Mandarin orange
    "elma": 0.105,  # Apple
    "armut": 0.220,  # Pear
    "seftale": 0.185,  # Peach
    "nar": 0.300,  # Pomegranate
    "agac": 0.0,   # Tree (weight not applicable)
}

# Fruit detection model files (relative to models directory)
FRUIT_MODEL_FILES: Dict[str, str] = {
    "mandalina": "mandalina.pt",
    "elma": "elma.pt",
    "armut": "armut.pt",
    "seftale": "seftale.pt",
    "nar": "nar.pt",
    "agac": "agac.pt",
}

# Absolute paths to fruit models
MODELS_DIR = BASE_DIR / "models"
FRUIT_MODEL_PATHS: Dict[str, Path] = {
    fruit_type: MODELS_DIR / model_file
    for fruit_type, model_file in FRUIT_MODEL_FILES.items()
}

# ==============================================================================
# FILE UPLOAD CONFIGURATION
# ==============================================================================

# Maximum file sizes (in bytes)
MAX_DETECTION_FILE_SIZE = 10 * 1024 * 1024  # 10MB for fruit detection
MAX_DRONE_FILE_SIZE = 100 * 1024 * 1024  # 100MB for drone orthophotos

# Allowed file extensions
DETECTION_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "bmp"}
DRONE_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "tif", "tiff"}

# Allowed MIME types
DETECTION_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/bmp",
    "image/x-ms-bmp",
}
DRONE_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/x-tiff",
}

# ==============================================================================
# VALIDATION LIMITS
# ==============================================================================

# Tree parameter limits
MIN_TREE_COUNT = 1
MAX_TREE_COUNT = 100000
MIN_TREE_AGE = 0
MAX_TREE_AGE = 150

# ==============================================================================
# CACHE CONFIGURATION
# ==============================================================================

# Cache key prefixes
CACHE_PREFIX_PREDICTION = "farmvision:prediction"
CACHE_PREFIX_TASK = "farmvision:task"

# Cache timeouts (in seconds)
CACHE_TIMEOUT_PREDICTION = 86400  # 24 hours
CACHE_TIMEOUT_TASK = 3600  # 1 hour

# ==============================================================================
# INFERENCE CONFIGURATION
# ==============================================================================

# Default confidence threshold for YOLO inference
DETECTION_CONFIDENCE_THRESHOLD = 0.1

# Minimum confidence threshold allowed via API (güvenlik sınırı)
MIN_CONFIDENCE_THRESHOLD = 0.05

# Maximum confidence threshold allowed via API
MAX_CONFIDENCE_THRESHOLD = 0.95
