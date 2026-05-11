# -*- coding: utf-8 -*-
import logging

from django.contrib.staticfiles.storage import StaticFilesStorage

logger = logging.getLogger("django.contrib.staticfiles")
logger.setLevel(logging.ERROR)


class IgnoreDuplicatesStaticFilesStorage(StaticFilesStorage):

    def save(self, name, content, max_length=None):
        if self.exists(name):
            return name
        return super().save(name, content, max_length=max_length)


class R2MediaStorage:
    """
    Cloudflare R2 storage backend for Django media files.

    Wraps django-storages S3Boto3Storage configured for R2's S3-compatible API.
    Import is deferred so the class can live in storage.py without making
    boto3 a hard dependency when USE_R2=False.
    """

    def __new__(cls, *args, **kwargs):
        from storages.backends.s3boto3 import S3Boto3Storage
        return S3Boto3Storage(*args, **kwargs)
