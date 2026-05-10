from django.db import models
from django.utils import timezone


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "newsletter_subscribers"
        ordering = ["-subscribed_at"]

    def __str__(self):
        return self.email
