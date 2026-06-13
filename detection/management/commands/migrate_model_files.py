"""
One-time management command to reorganize model weights into versioned directories.

Usage:
    python manage.py migrate_model_files

For each fruit type, if models/<fruit>.pt exists:
    - Creates models/<fruit>/v1/
    - Moves models/<fruit>.pt  →  models/<fruit>/v1/weights.pt

Safe to run multiple times (idempotent).
"""
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

FRUIT_TYPES = ["mandalina", "elma", "armut", "seftale", "nar", "agac"]


class Command(BaseCommand):
    help = "Move flat model .pt files into versioned subdirectories (idempotent)."

    def handle(self, *args, **options):
        models_dir = Path(settings.BASE_DIR) / "models"

        if not models_dir.exists():
            self.stdout.write(self.style.WARNING(f"models/ directory not found at {models_dir}. Nothing to do."))
            return

        for fruit_type in FRUIT_TYPES:
            src = models_dir / f"{fruit_type}.pt"
            dest_dir = models_dir / fruit_type / "v1"
            dest = dest_dir / "weights.pt"

            if dest.exists():
                self.stdout.write(f"  SKIP  {fruit_type}: {dest} already exists.")
                continue

            if not src.exists():
                self.stdout.write(f"  SKIP  {fruit_type}: {src} not found.")
                continue

            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            self.stdout.write(self.style.SUCCESS(f"  MOVED {fruit_type}: {src} → {dest}"))

        self.stdout.write(self.style.SUCCESS("migrate_model_files complete."))
