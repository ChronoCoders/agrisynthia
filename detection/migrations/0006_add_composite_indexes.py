# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("detection", "0005_add_task_id"),
    ]

    operations = [
        # Add composite index for common query pattern: filter by fruit_type and order by created_at
        migrations.AddIndex(
            model_name="detectionresult",
            index=models.Index(
                fields=["fruit_type", "-created_at"], name="detection_fruit_created_idx"
            ),
        ),
        # Add composite index for filtering by tree_age and fruit_type
        migrations.AddIndex(
            model_name="detectionresult",
            index=models.Index(
                fields=["tree_age", "fruit_type"], name="detection_age_fruit_idx"
            ),
        ),
        # Add composite index for batch queries
        migrations.AddIndex(
            model_name="multidetectionbatch",
            index=models.Index(
                fields=["fruit_type", "-created_at"], name="batch_fruit_created_idx"
            ),
        ),
    ]
