# Generated migration for ScheduledReport model

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0001_initial"),
        ("dron_map", "0007_add_field_polygon_satellite_ndvi"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_type", models.CharField(choices=[("detection", "Tespit Raporu"), ("drone", "Drone Analiz Raporu")], max_length=20)),
                ("format", models.CharField(choices=[("pdf", "PDF"), ("xlsx", "Excel")], max_length=10)),
                ("frequency", models.CharField(choices=[("daily", "Günlük"), ("weekly", "Haftalık"), ("monthly", "Aylık")], max_length=10)),
                ("is_active", models.BooleanField(default=True)),
                ("last_sent", models.DateTimeField(blank=True, null=True)),
                ("next_run", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scheduled_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="scheduled_reports",
                        to="dron_map.projects",
                    ),
                ),
            ],
            options={
                "db_table": "scheduled_reports",
                "ordering": ["next_run"],
            },
        ),
    ]
