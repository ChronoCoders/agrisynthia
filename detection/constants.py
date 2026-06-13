from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).resolve().parent.parent

FRUIT_WEIGHTS: Dict[str, float] = {
    "mandalina": 0.125,
    "elma": 0.105,
    "armut": 0.220,
    "seftale": 0.185,
    "nar": 0.300,
    "agac": 0.0,
}

FRUIT_MODEL_FILES: Dict[str, str] = {
    "mandalina": "mandalina.pt",
    "elma": "elma.pt",
    "armut": "armut.pt",
    "seftale": "seftale.pt",
    "nar": "nar.pt",
    "agac": "agac.pt",
}

MODELS_DIR = BASE_DIR / "models"
FRUIT_MODEL_PATHS: Dict[str, Path] = {
    fruit_type: MODELS_DIR / model_file
    for fruit_type, model_file in FRUIT_MODEL_FILES.items()
}

MAX_DETECTION_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_DRONE_FILE_SIZE = 100 * 1024 * 1024  # 100MB

DETECTION_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "bmp"}
DRONE_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "tif", "tiff"}

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

MIN_TREE_COUNT = 1
MAX_TREE_COUNT = 100000
MIN_TREE_AGE = 0
MAX_TREE_AGE = 150

CACHE_PREFIX_PREDICTION = "agrisynthia:prediction"
CACHE_PREFIX_TASK = "agrisynthia:task"

CACHE_TIMEOUT_PREDICTION = 86400  # 24h
CACHE_TIMEOUT_TASK = 3600  # 1h

DETECTION_CONFIDENCE_THRESHOLD = 0.1

MIN_CONFIDENCE_THRESHOLD = 0.05
MAX_CONFIDENCE_THRESHOLD = 0.95
