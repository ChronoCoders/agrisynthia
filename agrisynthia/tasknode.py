# -*- coding: utf-8 -*-
"""
NodeODM client wrapper.

Thin wrapper around pyodm.Node that reads host/port/token from Django settings
so connection parameters are configurable via environment variables rather than
being hardcoded.
"""
import glob
import logging
import os
from pathlib import Path

from django.conf import settings
from pyodm import Node

BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)


def _get_node() -> Node:
    """Return a Node client using settings from Django configuration."""
    return Node(
        host=settings.ODM_HOST,
        port=settings.ODM_PORT,
        token=settings.ODM_TOKEN or None,
    )


class Node_processing:

    def __init__(self, image_dir):
        try:
            self.start_api = _get_node()
            self.task = self.create_node_task(image_folder=image_dir)
            self.uuid = self.task.uuid
        except Exception as e:
            logger.error("NodeODM connection error: %s", e)
            raise ConnectionError(
                f"NodeODM'e bağlanılamadı. Docker çalışıyor mu? Hata: {e}"
            )

    def create_node_task(self, image_folder):
        try:
            images = glob.glob(f"{image_folder}/*.JPG") + glob.glob(
                f"{image_folder}/*.jpg"
            )

            if not images:
                raise ValueError(f"Klasörde JPG dosyası bulunamadı: {image_folder}")

            task = self.start_api.create_task(
                images, {"dsm": True, "dtm": True, "odm": True}
            )
            logger.info("Task oluşturuldu: %s", task.uuid)
            return task
        except Exception as e:
            logger.error("Task oluşturma hatası: %s", e)
            raise

    def download_task(self, path):
        try:
            logger.info("Task bekleniyor: %s", self.task.uuid)
            self.task.wait_for_completion()

            os.makedirs(path, exist_ok=True)
            self.task.download_assets(path)
            logger.info("Sonuçlar indirildi: %s", path)
        except Exception as e:
            logger.error("İndirme hatası: %s", e)
            raise

    def get_uuid(self):
        return self.uuid

    def get_tasks(self, api):
        try:
            return self.start_api.get_task(api)
        except Exception as e:
            logger.error("Task bilgisi alınamadı: %s", e)
            return None

    def task_info(self):
        try:
            info = self.start_api.info()
            return {
                "version": info.version,
                "task_queue_count": info.task_queue_count,
                "max_images": info.max_images,
                "engine_version": info.engine_version,
                "engine": info.engine,
            }
        except Exception as e:
            logger.error("Info alınamadı: %s", e)
            return {}
