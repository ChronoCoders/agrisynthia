"""DEPRECATED — superseded by detection.models.ModelVersion. Kept for the
system monitoring view; delegates to the DB."""
import logging
import os
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def get_model_info(model_name: str) -> Optional[Dict[str, Any]]:
    """Return metadata for a model file name (e.g. 'mandalina.pt'). Deprecated."""
    fruit_type = model_name.replace(".pt", "")
    try:
        from detection.models import ModelVersion
        mv = ModelVersion.get_active(fruit_type)
        return {
            "version": mv.version,
            "framework": mv.framework,
            "weights_path": mv.weights_path,
            "is_active": mv.is_active,
        }
    except Exception:
        return None


def get_all_models() -> Dict[str, Dict[str, Any]]:
    """Return metadata dict for all active model versions. Deprecated."""
    try:
        from detection.models import ModelVersion
        result = {}
        for mv in ModelVersion.objects.filter(is_active=True):
            result[f"{mv.fruit_type}.pt"] = {
                "version": mv.version,
                "framework": mv.framework,
                "weights_path": mv.weights_path,
            }
        return result
    except Exception:
        return {}


def get_loaded_models_info() -> List[Dict[str, Any]]:
    """Return model status list for the system monitoring view."""
    try:
        from detection.models import ModelVersion
        models_dir = os.path.join(settings.BASE_DIR, "models")
        loaded_models = []

        for mv in ModelVersion.objects.filter(is_active=True).order_by("fruit_type"):
            weights_abs = os.path.join(settings.BASE_DIR, mv.weights_path)
            legacy_abs = os.path.join(models_dir, f"{mv.fruit_type}.pt")
            is_exists = os.path.exists(weights_abs) or os.path.exists(legacy_abs)

            loaded_models.append(
                {
                    "model_id": f"{mv.fruit_type}.pt",
                    "is_loaded": is_exists,
                    "version": mv.version,
                    "date": mv.created_at.strftime("%Y-%m-%d"),
                    "accuracy": None,
                    "description": mv.notes or f"{mv.fruit_type} model ({mv.framework})",
                    "framework": mv.framework,
                    "input_size": 640,
                }
            )
        return loaded_models
    except Exception as exc:
        logger.warning("get_loaded_models_info fell back to empty list: %s", exc)
        return []
