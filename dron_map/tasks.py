# -*- coding: utf-8 -*-
"""
Celery tasks for ODM (NodeODM) processing.

Flow:
  1. User uploads drone images via the add-project form.
  2. Images are saved to disk synchronously.
  3. process_odm_task is dispatched as a Celery task (async).
  4. The task creates a NodeODM task, polls for completion, then downloads
     the output assets into static/results/{hashing_path}/.
  5. Project.odm_status is updated at each step so the frontend can poll.
"""
import logging
import os
from pathlib import Path

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_DIR = Path(settings.BASE_DIR)


@shared_task(bind=True, max_retries=0, name="dron_map.process_odm_task")
def process_odm_task(self, project_id: int) -> dict:
    """
    Run NodeODM processing for a project.

    Args:
        project_id: Primary key of the dron_map.Projects instance.

    Returns:
        dict with keys: project_id, status, odm_task_id, output_path
    """
    from dron_map.models import Projects

    try:
        project = Projects.objects.get(pk=project_id)
    except Projects.DoesNotExist:
        logger.error("process_odm_task: proje bulunamadı pk=%s", project_id)
        return {"error": f"Proje bulunamadı: {project_id}"}

    if not settings.ODM_ENABLED:
        logger.info("ODM devre dışı; proje %s atlandı.", project_id)
        project.odm_status = Projects.ODM_DISABLED
        project.save(update_fields=["odm_status"])
        return {"project_id": project_id, "status": Projects.ODM_DISABLED}

    # Locate uploaded images — saved by the view into static/images_ortho/{hashing_path}
    image_dir = BASE_DIR / "static" / "images_ortho" / project.hashing_path
    output_dir = BASE_DIR / "static" / "results" / project.hashing_path

    if not image_dir.exists():
        err = f"Görüntü dizini bulunamadı: {image_dir}"
        logger.error("process_odm_task proje %s: %s", project_id, err)
        project.odm_status = Projects.ODM_FAILED
        project.odm_error = err
        project.save(update_fields=["odm_status", "odm_error"])
        return {"project_id": project_id, "error": err}

    # Mark as processing
    project.odm_status = Projects.ODM_PROCESSING
    project.save(update_fields=["odm_status"])

    try:
        from pyodm import Node
        from pyodm.exceptions import TaskFailedError

        node = Node(
            host=settings.ODM_HOST,
            port=settings.ODM_PORT,
            token=settings.ODM_TOKEN or None,
        )

        # Collect image files
        import glob as glob_mod
        images = (
            glob_mod.glob(str(image_dir / "*.JPG"))
            + glob_mod.glob(str(image_dir / "*.jpg"))
            + glob_mod.glob(str(image_dir / "*.PNG"))
            + glob_mod.glob(str(image_dir / "*.png"))
        )

        if not images:
            raise ValueError(f"Klasörde desteklenen görüntü bulunamadı: {image_dir}")

        logger.info(
            "ODM task başlatılıyor — proje %s, %d görüntü, host=%s:%s",
            project_id, len(images), settings.ODM_HOST, settings.ODM_PORT,
        )

        task = node.create_task(
            images,
            options={"dsm": True, "dtm": True, "orthophoto-resolution": 5},
        )

        project.odm_task_id = task.uuid
        project.save(update_fields=["odm_task_id"])
        logger.info("ODM task oluşturuldu: %s (proje %s)", task.uuid, project_id)

        # Block until ODM finishes (runs in Celery worker, not in web process)
        task.wait_for_completion()

        # Download results
        output_dir.mkdir(parents=True, exist_ok=True)
        task.download_assets(str(output_dir))
        logger.info("ODM sonuçları indirildi: %s (proje %s)", output_dir, project_id)

        project.odm_status = Projects.ODM_COMPLETED
        project.odm_error = None
        project.save(update_fields=["odm_status", "odm_error"])

        return {
            "project_id": project_id,
            "status": Projects.ODM_COMPLETED,
            "odm_task_id": task.uuid,
            "output_path": str(output_dir),
        }

    except Exception as e:
        logger.error(
            "ODM işleme hatası proje %s: %s", project_id, e, exc_info=True
        )
        project.odm_status = Projects.ODM_FAILED
        project.odm_error = str(e)
        project.save(update_fields=["odm_status", "odm_error"])
        return {"project_id": project_id, "error": str(e)}
