# Generated migration for confidence score tracking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("detection", "0003_alter_detectionresult_created_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="detectionresult",
            name="confidence_score",
            field=models.FloatField(
                blank=True,
                help_text="Average confidence score from YOLO detection",
                null=True,
            ),
        ),
    ]
