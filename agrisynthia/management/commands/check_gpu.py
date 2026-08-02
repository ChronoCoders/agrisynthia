"""Report whether the running process can see a CUDA device.

Runs at container start rather than at build time. `docker build` has no GPU
access, so asserting on torch.cuda.is_available() in a RUN step only passes
when the daemon's default runtime happens to be nvidia.

Default behaviour is advisory: it logs loudly and exits 0 so a CPU-only host
can still boot and serve the site, admin, and API. Pass --require to make it
exit non-zero, which is the right choice for a worker that should refuse to
start rather than silently run inference on CPU.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Report CUDA availability for the running process."

    def add_arguments(self, parser):
        parser.add_argument(
            "--require",
            action="store_true",
            help="Exit non-zero when no CUDA device is visible.",
        )

    def handle(self, *args, **options):
        require = options["require"]

        try:
            import torch
        except Exception as exc:
            msg = f"torch is not importable: {exc}"
            if require:
                self.stderr.write(self.style.ERROR(f"GPU check failed: {msg}"))
                raise SystemExit(1)
            self.stderr.write(self.style.WARNING(f"GPU check skipped: {msg}"))
            return

        available = torch.cuda.is_available()

        if not available:
            msg = (
                "No CUDA device visible. Inference will fall back to CPU and be "
                "very slow. Check that the host has the NVIDIA Container Toolkit "
                "and that the service reserves a GPU device."
            )
            if require:
                self.stderr.write(self.style.ERROR(f"GPU check failed: {msg}"))
                raise SystemExit(1)
            self.stderr.write(self.style.WARNING(f"GPU check: {msg}"))
            return

        count = torch.cuda.device_count()
        names = ", ".join(torch.cuda.get_device_name(i) for i in range(count))
        self.stdout.write(
            self.style.SUCCESS(
                f"GPU check: {count} device(s) visible [{names}], "
                f"torch {torch.__version__}, CUDA {torch.version.cuda}"
            )
        )
