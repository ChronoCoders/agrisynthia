import gzip
import shutil
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate and compress API schema"

    def handle(self, *args, **options):
        static_dir = Path("static")
        static_dir.mkdir(exist_ok=True)

        schema_path = static_dir / "schema.yml"
        gz_path = static_dir / "schema.yml.gz"

        self.stdout.write("Generating schema...")
        call_command("spectacular", "--file", str(schema_path))

        if not schema_path.exists():
            self.stdout.write(self.style.ERROR("Schema generation failed"))
            return

        self.stdout.write("Compressing schema...")
        with open(schema_path, "rb") as f_in:
            with gzip.open(gz_path, "wb", compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)

        original_size = schema_path.stat().st_size
        compressed_size = gz_path.stat().st_size
        ratio = (1 - compressed_size / original_size) * 100

        self.stdout.write(self.style.SUCCESS("Schema generated successfully"))
        self.stdout.write(f"Original: {original_size:,} bytes")
        self.stdout.write(f"Compressed: {compressed_size:,} bytes")
        self.stdout.write(f"Saved: {ratio:.1f}%")
