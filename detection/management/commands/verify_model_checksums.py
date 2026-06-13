from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from agrisynthia.predict_tree import compute_sha256
from detection.models import ModelVersion


class Command(BaseCommand):
    help = "Compute and verify SHA256 checksums for active ModelVersion weights."

    def add_arguments(self, parser):
        parser.add_argument(
            "--store",
            action="store_true",
            help="Store the computed checksum on ModelVersion rows that lack one. "
                 "Refuses to overwrite an existing checksum (use --force to allow).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow --store to overwrite an existing checksum.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit non-zero on any mismatch or missing file.",
        )
        parser.add_argument(
            "--fruit",
            default=None,
            help="Only check a single fruit type (default: all active).",
        )

    def handle(self, *args, **opts):
        base = Path(settings.BASE_DIR)
        qs = ModelVersion.objects.filter(is_active=True)
        if opts["fruit"]:
            qs = qs.filter(fruit_type=opts["fruit"])

        problems = 0
        for mv in qs.order_by("fruit_type"):
            path = base / mv.weights_path
            if not path.exists():
                self.stdout.write(self.style.ERROR(
                    f"MISSING  {mv.fruit_type} {mv.version}  {mv.weights_path}"
                ))
                problems += 1
                continue

            self.stdout.write(f"hashing  {mv.fruit_type} {mv.version}  ({path.stat().st_size / (1024*1024):.1f} MB) …", ending="")
            self.stdout.flush()
            actual = compute_sha256(path)
            self.stdout.write(f" {actual}")

            stored = (mv.checksum_sha256 or "").lower()
            if not stored:
                if opts["store"]:
                    mv.checksum_sha256 = actual
                    mv.save(update_fields=["checksum_sha256"])
                    self.stdout.write(self.style.SUCCESS(f"  stored on ModelVersion"))
                else:
                    self.stdout.write(self.style.WARNING(f"  (no stored checksum — run with --store to backfill)"))
            elif stored == actual:
                self.stdout.write(self.style.SUCCESS(f"  OK"))
            else:
                self.stdout.write(self.style.ERROR(
                    f"  MISMATCH — stored {stored} != actual {actual}"
                ))
                problems += 1
                if opts["store"] and opts["force"]:
                    mv.checksum_sha256 = actual
                    mv.save(update_fields=["checksum_sha256"])
                    self.stdout.write(self.style.WARNING(f"  overwrote stored checksum (--force)"))

        if problems:
            self.stdout.write(self.style.ERROR(f"\n{problems} problem(s) found."))
            if opts["strict"]:
                raise SystemExit(1)
        else:
            self.stdout.write(self.style.SUCCESS(f"\nAll active models verified."))
