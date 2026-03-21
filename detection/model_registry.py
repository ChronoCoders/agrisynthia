# -*- coding: utf-8 -*-
"""
Model Registry for tracking ML model versions and metadata
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Model metadata registry
MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "mandalina.pt": {
        "version": "1.0.0",
        "date": datetime(2024, 1, 15),
        "accuracy": 0.92,
        "description": "Mandalina meyve algılama modeli",
        "training_dataset_size": 5000,
        "framework": "YOLOv5",
        "input_size": 640,
        "confidence_threshold": 0.1,
        "iou_threshold": 0.45,
    },
    "elma.pt": {
        "version": "1.0.0",
        "date": datetime(2024, 1, 15),
        "accuracy": 0.89,
        "description": "Elma meyve algılama modeli",
        "training_dataset_size": 4800,
        "framework": "YOLOv5",
        "input_size": 640,
        "confidence_threshold": 0.1,
        "iou_threshold": 0.45,
    },
    "armut.pt": {
        "version": "1.0.0",
        "date": datetime(2024, 1, 15),
        "accuracy": 0.88,
        "description": "Armut meyve algılama modeli",
        "training_dataset_size": 4500,
        "framework": "YOLOv5",
        "input_size": 640,
        "confidence_threshold": 0.1,
        "iou_threshold": 0.45,
    },
    "seftale.pt": {
        "version": "1.0.0",
        "date": datetime(2024, 1, 15),
        "accuracy": 0.90,
        "description": "Şeftali meyve algılama modeli",
        "training_dataset_size": 4600,
        "framework": "YOLOv5",
        "input_size": 640,
        "confidence_threshold": 0.1,
        "iou_threshold": 0.45,
    },
    "nar.pt": {
        "version": "1.0.0",
        "date": datetime(2024, 1, 15),
        "accuracy": 0.91,
        "description": "Nar meyve algılama modeli",
        "training_dataset_size": 4700,
        "framework": "YOLOv5",
        "input_size": 640,
        "confidence_threshold": 0.1,
        "iou_threshold": 0.45,
    },
    "agac.pt": {
        "version": "1.0.0",
        "date": datetime(2024, 1, 15),
        "accuracy": 0.87,
        "description": "Ağaç algılama modeli",
        "training_dataset_size": 3500,
        "framework": "YOLOv5",
        "input_size": 640,
        "confidence_threshold": 0.25,
        "iou_threshold": 0.7,
    },
}


def get_model_info(model_name: str) -> Optional[Dict[str, Any]]:
    """
    Get metadata for a specific model

    Args:
        model_name: Name of the model file (e.g., 'mandalina.pt')

    Returns:
        Dictionary with model metadata or None if model not found
    """
    return MODEL_REGISTRY.get(model_name)


def get_all_models() -> Dict[str, Dict[str, Any]]:
    """
    Get metadata for all registered models

    Returns:
        Dictionary mapping model names to their metadata
    """
    return MODEL_REGISTRY.copy()


def get_loaded_models_info() -> list:
    """
    Get information about all loaded/registered models

    Returns:
        List of dictionaries containing model information with model_id and is_loaded status
    """
    loaded_models = []
    models_dir = os.path.join(settings.BASE_DIR, "models")
    
    for model_name, info in MODEL_REGISTRY.items():
        model_path = os.path.join(models_dir, model_name)
        is_exists = os.path.exists(model_path)
        
        loaded_models.append(
            {
                "model_id": model_name,
                "is_loaded": is_exists,
                "version": info["version"],
                "date": info["date"].strftime("%Y-%m-%d"),
                "accuracy": info["accuracy"],
                "description": info["description"],
                "framework": info.get("framework", "Unknown"),
                "input_size": info.get("input_size", 0),
            }
        )
    return loaded_models
