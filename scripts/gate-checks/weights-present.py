#!/usr/bin/env python
"""Fail unless every fruit model's weights file is present and non empty.

The fruit types are enumerated from detection/constants.py, not from a list
written here. A hand written list in the checker would drift from the code it
is meant to guard, and it would silently stop covering a model added later.

This exists because detection/test_inference.py skips itself when weights are
absent, and a skip is not a failure. Without this step the gate would pass on a
machine with no models at all.

Note on the path: constants.FRUIT_MODEL_PATHS points at the flat legacy
models/<fruit>.pt layout, which migrate_model_files moves away from. The live
layout, written by 0012_seed_model_versions into ModelVersion.weights_path, is
models/<fruit>/v1/weights.pt, so that is what is checked.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from detection.constants import FRUIT_WEIGHTS  # noqa: E402

VERSION = "v1"


def weights_path(fruit_type: str) -> Path:
    return ROOT / "models" / fruit_type / VERSION / "weights.pt"


def main() -> int:
    fruit_types = sorted(FRUIT_WEIGHTS)
    if not fruit_types:
        print("no fruit types found in detection.constants, refusing to report")
        return 1

    print(f"{len(fruit_types)} fruit types from detection.constants.FRUIT_WEIGHTS")
    missing = []
    for fruit_type in fruit_types:
        path = weights_path(fruit_type)
        try:
            size = path.stat().st_size
        except OSError:
            print(f"MISSING  {fruit_type:<12} {path.relative_to(ROOT)}")
            missing.append(fruit_type)
            continue
        if size == 0:
            print(f"EMPTY    {fruit_type:<12} {path.relative_to(ROOT)}")
            missing.append(fruit_type)
        else:
            print(f"ok       {fruit_type:<12} {size / 1048576:8.1f} MB")

    if missing:
        print()
        print(f"{len(missing)} model(s) unusable: {', '.join(missing)}")
        print("Run: python manage.py migrate_model_files")
        print("then: python manage.py verify_model_checksums --store")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
