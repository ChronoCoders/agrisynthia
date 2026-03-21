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
