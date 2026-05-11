# -*- coding: utf-8 -*-
import hashlib
import os
from pathlib import Path

from django.db import migrations

FRUIT_TYPES = ["mandalina", "elma", "armut", "seftale", "nar", "agac"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def seed_model_versions(apps, schema_editor):
    ModelVersion = apps.get_model("detection", "ModelVersion")
    base_dir = Path(__file__).resolve().parent.parent.parent  # project root

    for fruit_type in FRUIT_TYPES:
        legacy_path = base_dir / "models" / f"{fruit_type}.pt"
        versioned_path = base_dir / "models" / fruit_type / "v1" / "weights.pt"

        if versioned_path.exists():
            checksum = _sha256(versioned_path)
        elif legacy_path.exists():
            checksum = _sha256(legacy_path)
        else:
            checksum = ""

        ModelVersion.objects.get_or_create(
            fruit_type=fruit_type,
            version="v1",
            defaults={
                "weights_path": f"models/{fruit_type}/v1/weights.pt",
                "framework": "YOLOv7",
                "is_active": True,
                "checksum_sha256": checksum,
                "notes": "Initial version seeded from migration.",
            },
        )


def unseed_model_versions(apps, schema_editor):
    ModelVersion = apps.get_model("detection", "ModelVersion")
    ModelVersion.objects.filter(version="v1").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("detection", "0011_add_model_version"),
    ]

    operations = [
        migrations.RunPython(seed_model_versions, reverse_code=unseed_model_versions),
    ]
