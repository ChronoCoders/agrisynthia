# -*- coding: utf-8 -*-
# Generated migration for adding task_id field to DetectionResult model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("detection", "0004_add_confidence_score"),
    ]

    operations = [
        migrations.AddField(
            model_name="detectionresult",
            name="task_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Celery task ID for async processing",
                max_length=255,
                null=True,
            ),
        ),
    ]
