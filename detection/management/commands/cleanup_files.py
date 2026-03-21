# -*- coding: utf-8 -*-
import logging
import os
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete files in static/detected/ older than 24 hours"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Delete files older than this many hours (default: 24)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        dry_run = options["dry_run"]

        # Calculate the cutoff time (current time - specified hours)
        cutoff_time = time.time() - (hours * 3600)

        # Get the path to static/detected/
        base_dir = settings.BASE_DIR
        detected_dir = Path(base_dir) / "static" / "detected"

        if not detected_dir.exists():
            self.stdout.write(
                self.style.WARNING(f"Directory does not exist: {detected_dir}")
            )
            return

        deleted_count = 0
        deleted_size = 0
        skipped_count = 0

        self.stdout.write(f"Scanning directory: {detected_dir}")
        self.stdout.write(f"Deleting files older than {hours} hours")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No files will be deleted")
            )

        try:
            # Walk through all subdirectories
            for root, dirs, files in os.walk(detected_dir):
                for filename in files:
                    file_path = Path(root) / filename

                    try:
                        # Get file modification time
                        file_mtime = os.path.getmtime(file_path)

                        # Check if file is older than cutoff time
                        if file_mtime < cutoff_time:
                            file_size = os.path.getsize(file_path)
                            file_age_hours = (time.time() - file_mtime) / 3600

                            if dry_run:
                                self.stdout.write(
                                    f"Would delete: {file_path} "
                                    f"(age: {file_age_hours:.1f}h, size: {file_size} bytes)"
                                )
                            else:
                                os.unlink(file_path)
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"Deleted: {file_path} "
                                        f"(age: {file_age_hours:.1f}h, size: {file_size} bytes)"
                                    )
                                )
                                logger.info("Deleted old file: %s", file_path)

                            deleted_count += 1
                            deleted_size += file_size
                        else:
                            skipped_count += 1

                    except (OSError, IOError) as e:
                        self.stdout.write(
                            self.style.ERROR(f"Error processing file {file_path}: {e}")
                        )
                        logger.error("Error processing file %s: %s", file_path, e)

                # Clean up empty directories (only if not dry run)
                if not dry_run:
                    for dirname in dirs:
                        dir_path = Path(root) / dirname
                        try:
                            # Try to remove directory if empty (rmdir only works on empty dirs)
                            if dir_path.exists():
                                dir_path.rmdir()
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"Removed empty directory: {dir_path}"
                                    )
                                )
                                logger.info("Removed empty directory: %s", dir_path)
                        except (OSError, IOError):
                            # Directory not empty or other error, skip silently
                            pass

            # Print summary
            self.stdout.write("-" * 70)
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"DRY RUN: Would delete {deleted_count} files "
                        f"({deleted_size / (1024*1024):.2f} MB)"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Cleanup complete: Deleted {deleted_count} files "
                        f"({deleted_size / (1024*1024):.2f} MB)"
                    )
                )

            self.stdout.write(f"Skipped {skipped_count} files (not old enough)")

            if not dry_run:
                logger.info(
                    f"Cleanup completed: deleted {deleted_count} files, "
                    f"{deleted_size / (1024*1024):.2f} MB"
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Cleanup failed: {e}"))
            logger.error("Cleanup failed: %s", e)
            raise
