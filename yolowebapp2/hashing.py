# -*- coding: utf-8 -*-
from hashlib import shake_256
from pathlib import Path
from time import localtime

BASE_DIR = Path(__file__).resolve().parent.parent


def add_prefix(filename):
    prefix = shake_256(f"{localtime()}{filename}".encode("utf-8")).hexdigest(20)
    return f"{BASE_DIR}/static/images_ortho/{prefix}", prefix


def add_prefix2(filename):
    prefix = shake_256(f"{localtime()}{filename}".encode("utf-8")).hexdigest(20)
    return f"{BASE_DIR}/static/images_counting/{prefix}", prefix
