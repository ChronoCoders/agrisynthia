# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.db import models


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

    # ODM processing state
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

    def __str__(self):
        return self.Farm
