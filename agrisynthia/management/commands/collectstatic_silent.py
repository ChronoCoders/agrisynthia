# -*- coding: utf-8 -*-
from django.contrib.staticfiles.management.commands.collectstatic import (
    Command as CollectStaticCommand,
)


class Command(CollectStaticCommand):

    def log(self, msg, level=2):
        if (
            "Found another file with the destination path" in msg
            and "fontawesomefree" in msg
        ):
            return
        super().log(msg, level)
