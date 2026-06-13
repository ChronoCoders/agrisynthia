from django.db import models
from django.utils import timezone


class ChatLead(models.Model):
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "chat_leads"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "newsletter_subscribers"
        ordering = ["-subscribed_at"]

    def __str__(self):
        return self.email
