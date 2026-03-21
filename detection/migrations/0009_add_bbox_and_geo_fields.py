from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("detection", "0008_add_model_version_threshold"),
    ]

    operations = [
        migrations.AddField(
            model_name="detectionresult",
            name="bbox_coordinates",
            field=models.JSONField(
                null=True,
                blank=True,
                help_text="List of detection bounding box center coordinates in pixels: [{'x': int, 'y': int}, ...]",
            ),
        ),
    ]

