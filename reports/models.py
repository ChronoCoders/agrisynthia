from django.db import models
from django.contrib.auth.models import User


class GeneratedReport(models.Model):
    REPORT_TYPE_CHOICES = [
        ("detection", "Tespit Raporu"),
        ("drone", "Drone Analiz Raporu"),
    ]
    FORMAT_CHOICES = [
        ("pdf", "PDF"),
        ("xlsx", "Excel"),
    ]
    STATUS_CHOICES = [
        ("pending", "Bekliyor"),
        ("processing", "İşleniyor"),
        ("ready", "Hazır"),
        ("failed", "Hata"),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, db_index=True)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    detection_result = models.ForeignKey(
        "detection.DetectionResult", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reports",
    )
    project = models.ForeignKey(
        "dron_map.Projects", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reports",
    )
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )
    file_path = models.CharField(max_length=500, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "generated_reports"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_report_type_display()} — {self.get_format_display()} — {self.status}"


class ScheduledReport(models.Model):
    FREQUENCY_CHOICES = [
        ("daily", "Günlük"),
        ("weekly", "Haftalık"),
        ("monthly", "Aylık"),
    ]
    REPORT_TYPE_CHOICES = GeneratedReport.REPORT_TYPE_CHOICES
    FORMAT_CHOICES = GeneratedReport.FORMAT_CHOICES

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scheduled_reports")
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    project = models.ForeignKey(
        "dron_map.Projects", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="scheduled_reports",
    )
    is_active = models.BooleanField(default=True)
    last_sent = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "scheduled_reports"
        ordering = ["next_run"]

    def __str__(self):
        return f"{self.user} — {self.get_report_type_display()} {self.get_frequency_display()}"
