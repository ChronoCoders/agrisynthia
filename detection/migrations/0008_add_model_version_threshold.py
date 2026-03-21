from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("detection", "0007_remove_detectionresult_detection_fruit_created_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="detectionresult",
            name="model_version",
            field=models.CharField(
                max_length=50,
                null=True,
                blank=True,
                db_index=True,
                help_text="Model file name and version used for this detection, e.g. mandalina.pt v1.0.0",
            ),
        ),
        migrations.AddField(
            model_name="detectionresult",
            name="threshold_used",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text="Confidence threshold used during inference",
            ),
        ),
    ]

