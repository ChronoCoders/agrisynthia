import os

from django.contrib.auth.models import User

# Set GEODJANGO_ENABLED=False in .env on Windows without OSGeo4W.
if os.environ.get("GEODJANGO_ENABLED", "True") == "True":
    from django.contrib.gis.db import models
    _USE_GIS = True
else:
    from django.db import models
    _USE_GIS = False


class Projects(models.Model):
    id: models.AutoField = models.AutoField(
        auto_created=True, primary_key=True, serialize=False
    )
    Farm: models.CharField = models.CharField(
        max_length=250, verbose_name="Farm", db_index=True
    )
    Field: models.CharField = models.CharField(
        max_length=250, verbose_name="Field", db_index=True
    )
    Title: models.CharField = models.CharField(max_length=250, verbose_name="Title")
    State: models.CharField = models.CharField(
        max_length=250, verbose_name="State", db_index=True
    )
    Data_time: models.DateTimeField = models.DateTimeField(
        auto_now_add=True, db_index=True
    )
    updated_at: models.DateTimeField = models.DateTimeField(
        auto_now=True, db_index=True
    )
    picture: models.FileField = models.FileField(
        upload_to="assets/images", blank=True, null=True, verbose_name="image"
    )
    hashing_path: models.CharField = models.CharField(
        max_length=250, verbose_name="Hashing Path"
    )
    created_by: models.ForeignKey = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="projects",
        db_index=True,
    )

    ODM_PENDING = "pending"
    ODM_PROCESSING = "processing"
    ODM_COMPLETED = "completed"
    ODM_FAILED = "failed"
    ODM_DISABLED = "disabled"
    ODM_STATUS_CHOICES = [
        (ODM_PENDING, "Bekliyor"),
        (ODM_PROCESSING, "İşleniyor"),
        (ODM_COMPLETED, "Tamamlandı"),
        (ODM_FAILED, "Başarısız"),
        (ODM_DISABLED, "Devre Dışı"),
    ]
    odm_task_id: models.CharField = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="NodeODM task UUID",
    )
    odm_status: models.CharField = models.CharField(
        max_length=20,
        choices=ODM_STATUS_CHOICES,
        default=ODM_PENDING,
        db_index=True,
    )
    odm_error: models.TextField = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if ODM processing failed",
    )

    field_polygon = (
        models.PolygonField(
            null=True,
            blank=True,
            srid=4326,
            help_text="WGS-84 polygon defining the field boundary",
        )
        if _USE_GIS
        else models.JSONField(
            null=True,
            blank=True,
            help_text="GeoJSON polygon ring [[lng, lat], ...] defining the field boundary",
        )
    )

    def __str__(self):
        return self.Farm


class SatelliteNDVI(models.Model):
    """One Sentinel-2 NDVI reading per project per scene date."""

    project = models.ForeignKey(
        Projects, on_delete=models.CASCADE, related_name="ndvi_readings"
    )
    date = models.DateField(db_index=True)
    mean_ndvi = models.FloatField()
    min_ndvi = models.FloatField()
    max_ndvi = models.FloatField()
    std_ndvi = models.FloatField()
    cloud_cover = models.FloatField(null=True, blank=True)
    scene_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("project", "date")]
        ordering = ["date"]

    def __str__(self):
        return f"{self.project} – {self.date} NDVI={self.mean_ndvi:.3f}"
